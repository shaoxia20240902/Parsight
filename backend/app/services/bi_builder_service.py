"""BI builder dialogue orchestrator.

The service owns workflow decisions only. Data context, existing report matching,
session state and chart creation are delegated to dedicated modules.
"""

from __future__ import annotations

import uuid
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai_service import AIService
from app.services.bi_builder_context import BIBuilderContextAssembler, BuilderContext
from app.services.bi_builder_creator import BIBuilderCreator
from app.services.bi_builder_matcher import ExistingReportMatcher
from app.services.bi_builder_state import BIBuilderStateStore
from app.services.db_service import DBService


@dataclass
class IntentResult:
    intent: str
    force_create: bool = False
    explore_dataset: bool = False
    requires_existing_match: bool = True
    confidence: float = 0.0
    reason: str = ""


class BIBuilderService:
    def __init__(self, db_service: DBService):
        self.db = db_service
        self.contexts = BIBuilderContextAssembler(db_service)
        self.state = BIBuilderStateStore(db_service)
        self.matcher = ExistingReportMatcher()
        self.creator = BIBuilderCreator(db_service)
        self.ai = AIService()

    async def handle(self, req: Any) -> Dict[str, Any]:
        event = getattr(req, "event", None) or {}
        event_type = event.get("type", "user_message")
        payload = event.get("payload") or {}
        message = (getattr(req, "message", "") or "").strip()
        space_id = getattr(req, "space_id", None)

        session = await self.state.load_or_create(getattr(req, "session_id", None), req.file_id, space_id)
        context = await self.contexts.load(req.file_id, space_id)
        blocked = self._blocked_reply(context)
        if blocked:
            return self._with_session(session["id"], blocked)

        if event_type != "user_message":
            response = await self._handle_event(event_type, payload, message, session, context)
            return self._with_session(session["id"], response)

        intent = await self._route_intent(message, payload, session, context)
        if intent.intent == "non_bi":
            await self.state.save(session, state="non_bi_answered")
            return self._with_session(session["id"], self._default_reply())

        if intent.force_create or intent.explore_dataset:
            response = await self._run_scope_planning(message, session, context, intent, force_new=intent.force_create)
            return self._with_session(session["id"], response)

        candidates = self.matcher.match(message, context)
        if candidates:
            await self.state.save(
                session,
                state="existing_candidate_shown",
                context_chart_id=candidates[0]["chart_id"],
            )
            return self._with_session(session["id"], self._existing_candidate_reply(candidates))

        response = await self._run_scope_planning(message, session, context, intent)
        return self._with_session(session["id"], response)

    async def _handle_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        message: str,
        session: Dict[str, Any],
        context: BuilderContext,
    ) -> Dict[str, Any]:
        if event_type == "adjust_existing":
            base_chart_id = payload.get("base_chart_id") or session.get("context_chart_id")
            await self.state.save(session, base_chart_id=base_chart_id)
            intent = IntentResult(intent="bi_modify", requires_existing_match=False)
            return await self._run_scope_planning(
                message or "基于已有图表调整",
                session,
                context,
                intent,
                base_chart_id=base_chart_id,
            )

        if event_type == "create_new":
            intent = IntentResult(intent="bi_create", force_create=True, requires_existing_match=False)
            return await self._run_scope_planning(message or "新建图表", session, context, intent, force_new=True)

        if event_type == "submit_questionnaire":
            form_values = payload.get("form_values") or payload
            chart_list = self._merge_form_values(session.get("chart_list") or [], form_values, context)
            await self.state.save(session, chart_list=chart_list)
            intent = IntentResult(intent="bi_supplement", requires_existing_match=False)
            return await self._run_scope_planning(message or "根据补充信息继续", session, context, intent)

        if event_type in {"confirm_knowledge", "confirm_preference"}:
            accepted = payload.get("accepted", True)
            card = payload.get("card") or {}
            if accepted:
                await self._persist_card(event_type, card, context)
            return await self._confirm_spec_reply(session, context)

        if event_type == "accept_chart_item":
            chart_list = list(session.get("chart_list") or [])
            item = payload.get("chart")
            if item:
                chart_list.append(item)
            await self.state.save(session, chart_list=chart_list)
            return await self._confirm_spec_reply(session, context)

        if event_type == "remove_chart_item":
            cid = payload.get("client_chart_id")
            chart_list = [c for c in session.get("chart_list") or [] if c.get("client_chart_id") != cid]
            await self.state.save(session, chart_list=chart_list)
            return await self._confirm_spec_reply(session, context)

        if event_type in {"modify_chart_list", "modify_fields", "modify_filters", "modify_category"}:
            intent = IntentResult(intent="bi_supplement", requires_existing_match=False)
            return await self._run_scope_planning(message or "调整图表配置", session, context, intent)

        if event_type == "confirm_generate":
            return await self._create_charts(session, context)

        return self._default_reply()

    async def _route_intent(
        self,
        message: str,
        payload: Dict[str, Any],
        session: Dict[str, Any],
        context: BuilderContext,
    ) -> IntentResult:
        override = payload.get("intent_override")
        if override:
            return IntentResult(
                intent=override,
                force_create=bool(payload.get("force_create")),
                requires_existing_match=not bool(payload.get("force_create")),
            )
        if payload.get("force_create"):
            return IntentResult(intent="bi_create", force_create=True, requires_existing_match=False)
        agent_result = await self._safe_agent_call(
            self.ai.route_bi_builder_intent,
            {
                "message": message,
                "session": self._compact_session(session),
                "context": self._compact_context(context),
            },
        )
        if agent_result and agent_result.get("intent"):
            return IntentResult(
                intent=agent_result.get("intent") or "non_bi",
                force_create=bool(agent_result.get("force_create")),
                explore_dataset=agent_result.get("intent") == "explore_dataset",
                requires_existing_match=bool(agent_result.get("requires_existing_match", True)),
                confidence=float(agent_result.get("confidence") or 0),
                reason=agent_result.get("reason") or "",
            )
        return self._fallback_intent(message, payload, session)

    async def _run_scope_planning(
        self,
        message: str,
        session: Dict[str, Any],
        context: BuilderContext,
        intent: IntentResult,
        force_new: bool = False,
        base_chart_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if intent.explore_dataset:
            directions = self._explore_directions(context)
            await self.state.save(
                session,
                state="scope_planning",
                scope_plan={"mode": "explore_dataset", "directions": directions},
                pending_input_ui={"type": "analysis_directions", "items": directions},
            )
            return {
                "state": "scope_planning",
                "reply": {
                    "content": "基于当前数据，我建议先从这些分析方向里选一个开始。",
                    "blocks": [
                        {"type": "analysis_directions", "items": directions},
                        {"type": "actions", "items": [
                            {"type": "create_new", "label": item["title"], "payload": {"message": item["prompt"], "force_create": True}}
                            for item in directions
                        ]},
                    ],
                },
                "scope_plan": {"directions": directions},
            }

        base_chart = self.matcher.find_chart(context, base_chart_id) if base_chart_id else None
        agent_plan = await self._safe_agent_call(
            self.ai.plan_bi_builder_scope,
            {
                "message": message,
                "intent": intent.__dict__,
                "force_new": force_new,
                "base_chart": base_chart,
                "current_chart_list": session.get("chart_list") or [],
                "context": self._compact_context(context),
            },
        )
        scope_plan = self._normalise_scope_plan(
            agent_plan,
            message,
            context,
            base_chart=base_chart,
            current_chart_list=session.get("chart_list") or [],
        )
        chart_list = scope_plan.get("chart_list") or []
        pending_ui = self._pending_input_ui(scope_plan, context)
        await self.state.save(
            session,
            state="scope_planning",
            scope_plan=scope_plan,
            chart_list=chart_list,
            pending_input_ui=pending_ui,
        )

        if scope_plan.get("missing_required"):
            return self._required_questionnaire_reply(context, scope_plan)

        cards = await self._knowledge_preference_cards(message, chart_list, context)
        if cards:
            knowledge_cards = [card for card in cards if card.get("card_type") == "business_knowledge"]
            preference_cards = [card for card in cards if card.get("card_type") == "user_preference"]
            await self.state.save(
                session,
                state="knowledge_preference_confirming",
                knowledge_cards=knowledge_cards,
                preference_cards=preference_cards,
            )
            return {
                "state": "knowledge_preference_confirming",
                "reply": {
                    "content": "需求已经确认清楚了。我识别到可能需要沉淀的业务知识或使用偏好，请先确认。",
                    "blocks": [{"type": "knowledge_cards", "items": cards}],
                },
                "scope_plan": scope_plan,
                "chart_list": chart_list,
            }

        return await self._confirm_spec_reply(session, context)

    def _normalise_scope_plan(
        self,
        agent_plan: Optional[Dict[str, Any]],
        message: str,
        context: BuilderContext,
        base_chart: Optional[Dict[str, Any]],
        current_chart_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if agent_plan and isinstance(agent_plan.get("chart_list"), list):
            plan = dict(agent_plan)
            plan.setdefault("mode", "chart_list")
            plan.setdefault("write_strategy", "adjust_existing" if base_chart else "append")
            plan.setdefault("missing_required", [])
            plan.setdefault("missing_advanced", [])
            plan.setdefault("recommended_categories", [])
            plan["chart_list"] = [self._normalise_draft(item, context, base_chart) for item in plan.get("chart_list") if isinstance(item, dict)]
            if plan["chart_list"]:
                plan.setdefault("readiness", 0.85)
                plan.setdefault("can_execute", True)
                return plan

        chart_list = current_chart_list or self._plan_chart_list(message, context, base_chart)
        missing = [] if chart_list else [{"field": "metric", "label": "指标"}, {"field": "dimension", "label": "维度"}]
        return {
            "readiness": 0.9 if chart_list else 0.4,
            "can_execute": bool(chart_list),
            "mode": "chart_list",
            "write_strategy": "adjust_existing" if base_chart else "append",
            "chart_list": chart_list,
            "missing_required": missing,
            "missing_advanced": [{"field": "time_range", "label": "时间范围"}],
            "recommended_categories": self._recommended_categories(chart_list, context),
            "impact": {"will_create": len(chart_list), "will_replace_existing": 0, "requires_rebuild_confirmation": False},
            "explain_for_user": "",
        }

    def _plan_chart_list(
        self,
        message: str,
        context: BuilderContext,
        base_chart: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if base_chart:
            return [self._draft_from_existing(message, base_chart)]

        profile, metric, dimension, time_field = self._best_fields(message, context)
        if not profile:
            return []
        text = message.lower()
        wants_trend = any(k in message for k in ("趋势", "按月", "月份", "月度", "走势")) and time_field
        wants_bottom = "bottom" in text or "倒数" in message or "最低" in message
        wants_top = "top" in text or "排名" in message or "前" in message or "最高" in message
        wants_table = "明细" in message or "列表" in message or "表格" in message

        chart_list: List[Dict[str, Any]] = []
        if wants_table:
            chart_list.append(self._draft("明细表", "detail", "table", profile, metric, dimension, time_field))
        elif wants_trend:
            chart_list.append(self._draft(f"{metric}月度趋势", "trend", "line", profile, metric, dimension, time_field))
        else:
            title = f"{dimension}{metric}{'Bottom 5' if wants_bottom else 'Top 5' if wants_top else '排名'}"
            chart_list.append(self._draft(title, "ranking_bottom" if wants_bottom else "ranking_top", "bar", profile, metric, dimension, time_field))
            if wants_top and not wants_bottom:
                companion = self._draft(f"{dimension}{metric}Bottom 5", "ranking_bottom", "bar", profile, metric, dimension, time_field)
                companion.update({
                    "required": False,
                    "source": "companion_recommendation",
                    "recommended_because": "与 Top 5 搭配可以同时看到头部贡献和尾部短板",
                })
                chart_list.append(companion)

        if "一组" in message or "看板" in message or "全部重新" in message:
            if time_field and not any(c["analysis_type"] == "trend" for c in chart_list):
                chart_list.append(self._draft(f"{metric}月度趋势", "trend", "line", profile, metric, dimension, time_field))
            chart_list.append(self._draft(f"{dimension}{metric}结构占比", "structure", "pie", profile, metric, dimension, time_field))
        return chart_list[:10]

    def _draft(
        self,
        title: str,
        analysis_type: str,
        chart_type: str,
        profile: Dict[str, Any],
        metric: str,
        dimension: str,
        time_field: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "client_chart_id": f"draft_{uuid.uuid4().hex[:8]}",
            "source": "user_request",
            "title": title,
            "analysis_type": analysis_type,
            "chart_type": chart_type,
            "target_category_id": self._category_id_for(profile),
            "table_name": profile["table_name"],
            "metric": {"field": metric, "aggregation": "sum", "label": metric},
            "dimensions": [dimension] if dimension else [],
            "time_field": time_field,
            "filters": [],
            "required": True,
            "write_mode": "append",
            "limit": 5 if analysis_type in {"ranking_top", "ranking_bottom"} else None,
        }

    def _draft_from_existing(self, message: str, chart: Dict[str, Any]) -> Dict[str, Any]:
        chart_type = chart.get("chart_type") or chart.get("type") or "bar"
        if "折线" in message:
            chart_type = "line"
        elif "柱" in message or "条形" in message:
            chart_type = "bar"
        elif "饼" in message:
            chart_type = "pie"
        return {
            "client_chart_id": f"draft_{uuid.uuid4().hex[:8]}",
            "source": "adjust_existing",
            "base_chart_id": chart.get("id"),
            "title": chart.get("title", "调整后的图表"),
            "analysis_type": chart.get("analysis_type") or "ranking_top",
            "chart_type": chart_type,
            "target_category_id": chart.get("category_id") or chart.get("categoryId"),
            "table_name": chart.get("table_name"),
            "metric": chart.get("metric") or {"field": chart.get("y_field") or "", "aggregation": "sum", "label": chart.get("y_field") or ""},
            "dimensions": chart.get("dimensions") or ([chart.get("x_field")] if chart.get("x_field") else []),
            "time_field": chart.get("time_field"),
            "filters": chart.get("filters") or [],
            "required": True,
            "write_mode": "adjust_existing",
        }

    async def _knowledge_preference_cards(
        self,
        message: str,
        chart_list: List[Dict[str, Any]],
        context: BuilderContext,
    ) -> List[Dict[str, Any]]:
        agent_result = await self._safe_agent_call(
            self.ai.detect_bi_builder_knowledge_preferences,
            {
                "message": message,
                "chart_list": chart_list,
                "context": self._compact_context(context),
            },
        )
        cards = agent_result.get("cards") if isinstance(agent_result, dict) else None
        if isinstance(cards, list):
            return cards

        fallback_cards = []
        for profile in context.profiles:
            for field in profile.get("fields", []):
                for value in field.get("sample_values", [])[:20]:
                    text = str(value)
                    short = text[:2]
                    if len(text) >= 4 and short in message and text not in message:
                        fallback_cards.append({
                            "card_type": "business_knowledge",
                            "title": f"是否把「{short}」记为「{text}」的业务别名？",
                            "payload": {
                                "term": short,
                                "canonical": text,
                                "knowledge_type": "alias",
                                "table_name": profile.get("table_name"),
                            },
                            "options": ["确认添加", "本次使用但不保存", "不是这个意思"],
                        })
                        return fallback_cards
        if "以后" in message or "默认" in message:
            fallback_cards.append({
                "card_type": "user_preference",
                "title": "是否保存这条使用偏好？",
                "payload": {"preference_key": "bi_builder_preference", "preference_value": message},
                "options": ["保存偏好", "仅本次使用", "不保存"],
            })
        return fallback_cards

    async def _persist_card(self, event_type: str, card: Dict[str, Any], context: BuilderContext) -> None:
        payload = card.get("payload") or card
        if event_type == "confirm_knowledge":
            term = payload.get("term")
            canonical = payload.get("canonical") or payload.get("mapped_to")
            if term and canonical:
                await self.db.save_business_knowledge(
                    file_id=context.file_id,
                    term=term,
                    canonical=canonical,
                    table_name=payload.get("table_name"),
                    knowledge_type=payload.get("knowledge_type") or "alias",
                    definition=payload.get("definition"),
                    scope=payload.get("scope") or "file",
                )
        if event_type == "confirm_preference":
            key = payload.get("preference_key") or "bi_builder_preference"
            value = payload.get("preference_value") or payload
            await self.db.save_user_preference(
                preference_key=key,
                preference_value=value,
                space_id=context.space_id,
            )

    async def _confirm_spec_reply(self, session: Dict[str, Any], context: BuilderContext) -> Dict[str, Any]:
        chart_list = session.get("chart_list") or (session.get("scope_plan") or {}).get("chart_list") or []
        if not chart_list:
            return self._required_questionnaire_reply(context, session.get("scope_plan") or {})

        scope_plan = session.get("scope_plan") or {}
        composed = await self._safe_agent_call(
            self.ai.compose_bi_builder_confirmation,
            {"chart_list": chart_list, "scope_plan": scope_plan, "context": self._compact_context(context)},
        )
        await self.state.save(session, state="confirming_spec")
        if composed and isinstance(composed.get("blocks"), list):
            return {"state": "confirming_spec", "reply": composed, "chart_list": chart_list, "scope_plan": scope_plan}

        return {
            "state": "confirming_spec",
            "reply": {
                "content": f"我将创建 {len(chart_list)} 张图表，请确认字段、筛选和分类。",
                "blocks": [
                    {"type": "markdown", "content": self._chart_list_markdown(chart_list)},
                    {"type": "actions", "items": [
                        {"type": "confirm_generate", "label": "确认生成"},
                        {"type": "modify_chart_list", "label": "增减图表"},
                        {"type": "modify_fields", "label": "调整字段"},
                        {"type": "modify_filters", "label": "调整筛选"},
                        {"type": "modify_category", "label": "调整分类"},
                    ]},
                ],
            },
            "chart_list": chart_list,
            "scope_plan": scope_plan,
        }

    async def _create_charts(self, session: Dict[str, Any], context: BuilderContext) -> Dict[str, Any]:
        chart_list = session.get("chart_list") or (session.get("scope_plan") or {}).get("chart_list") or []
        if not chart_list:
            return self._required_questionnaire_reply(context, session.get("scope_plan") or {})

        result = await self.creator.create(chart_list, context)
        created = result["created"]
        failed = result["failed"]
        await self.state.save(
            session,
            state="completed",
            created_chart_ids=[chart["id"] for chart in created],
        )

        blocks = []
        for chart in created:
            blocks.append({
                "type": "chart_summary",
                "chart_id": chart["id"],
                "title": chart["title"],
                "category_id": chart.get("category_id"),
                "chart_type": chart.get("chart_type"),
                "reason": "已创建",
            })
            blocks.append({"type": "chart_preview", "chart_id": chart["id"], "preview": chart.get("preview")})

        if failed:
            repair = await self._safe_agent_call(
                self.ai.suggest_bi_builder_repairs,
                {"failed": failed, "context": self._compact_context(context)},
            )
            blocks.append({
                "type": "markdown",
                "content": "部分图表未创建：\n" + "\n".join(f"- {f.get('title') or f.get('client_chart_id')}: {f['reason']}" for f in failed),
            })
            if repair and repair.get("repair_options"):
                blocks.append({"type": "actions", "items": repair["repair_options"]})

        if created:
            first = created[0]
            blocks.append({"type": "actions", "items": [
                {"type": "navigate", "label": "去查看", "target": "/bi", "params": {"category_id": first.get("category_id"), "chart_id": first.get("id")}}
            ]})

        return {
            "state": "completed",
            "reply": {"content": f"已创建 {len(created)} 张图表。", "blocks": blocks},
            "created_chart_ids": [chart["id"] for chart in created],
            "failed": failed,
        }

    def _required_questionnaire_reply(self, context: BuilderContext, scope_plan: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "state": "collecting_required_inputs",
            "reply": {
                "content": "还差几个必要信息，确认后就能生成。",
                "blocks": [
                    {"type": "questionnaire", "section": "required", "submit_label": "确认并继续", "questions": [
                        {"field": "metric", "label": "指标", "required": True, "control": "single_choice", "options": self._field_options(context, "metric")[:10]},
                        {"field": "dimension", "label": "分析维度", "required": True, "control": "single_choice", "options": self._field_options(context, "dimension")[:12]},
                    ]},
                    {"type": "advanced_panel", "collapsed": True, "questions": [
                        {"field": "limit", "label": "数量", "required": False, "control": "number_stepper", "default": 5},
                    ]},
                ],
            },
            "scope_plan": scope_plan,
        }

    def _existing_candidate_reply(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        first = candidates[0]
        return {
            "state": "existing_candidate_shown",
            "reply": {
                "content": "我找到一张很接近的已有图表。你可以直接查看，也可以基于它轻量调整，或者跳过复用直接新建。",
                "blocks": [
                    {"type": "chart_summary", **first},
                    {"type": "chart_preview", "chart_id": first["chart_id"]},
                    {"type": "actions", "items": [
                        {"type": "navigate", "label": "去查看", "target": "/bi", "params": {"category_id": first.get("category_id"), "chart_id": first.get("chart_id")}},
                        {"type": "adjust_existing", "label": "基于此图调整", "payload": {"base_chart_id": first.get("chart_id")}},
                        {"type": "create_new", "label": "我要新建", "payload": {"force_create": True}},
                    ]},
                ],
            },
            "matched_charts": candidates,
        }

    def _merge_form_values(
        self,
        chart_list: List[Dict[str, Any]],
        values: Dict[str, Any],
        context: BuilderContext,
    ) -> List[Dict[str, Any]]:
        if not chart_list:
            profile, metric, dimension, time_field = self._best_fields("", context)
            if not profile:
                return []
            chart_list = [self._draft("自定义图表", "ranking_top", "bar", profile, metric, dimension, time_field)]
        first = dict(chart_list[0])
        if values.get("metric"):
            first["metric"] = {"field": values["metric"], "aggregation": "sum", "label": values["metric"]}
        if values.get("dimension"):
            first["dimensions"] = [values["dimension"]]
        if values.get("limit"):
            first["limit"] = values["limit"]
        return [first] + chart_list[1:]

    def _pending_input_ui(self, scope_plan: Dict[str, Any], context: BuilderContext) -> Dict[str, Any]:
        if scope_plan.get("missing_required"):
            return {"type": "questionnaire", "section": "required"}
        if scope_plan.get("missing_advanced"):
            return {"type": "advanced_panel", "collapsed": True}
        return {}

    def _chart_list_markdown(self, chart_list: List[Dict[str, Any]]) -> str:
        lines = ["| 图表 | 类型 | 指标 | 维度 | 筛选 | 推荐分类 | 写入方式 |", "|---|---|---|---|---|---|---|"]
        for chart in chart_list:
            metric = (chart.get("metric") or {}).get("field") or "-"
            dims = "、".join(chart.get("dimensions") or []) or "-"
            filters = "、".join(str(item) for item in (chart.get("filters") or [])) or "-"
            lines.append(
                f"| {chart.get('title', '-')} | {chart.get('chart_type') or '-'} | {metric} | {dims} | {filters} | "
                f"{chart.get('target_category_id') or '-'} | {chart.get('write_mode') or 'append'} |"
            )
        return "\n".join(lines)

    def _fallback_intent(self, message: str, payload: Dict[str, Any], session: Dict[str, Any]) -> IntentResult:
        text = message.lower()
        if any(k in message for k in ("不要用已有", "重新创建", "新建", "重新做", "重做")):
            return IntentResult(intent="bi_create", force_create=True, requires_existing_match=False)
        if any(k in message for k in ("能做什么", "有什么分析", "推荐分析", "不知道做什么", "看看这个数据")):
            return IntentResult(intent="explore_dataset", explore_dataset=True, requires_existing_match=False)
        if session.get("context_chart_id") and any(k in message for k in ("加", "换", "改", "筛选", "时间", "分类", "图")):
            return IntentResult(intent="bi_supplement", requires_existing_match=False)
        if any(k in message for k in ("图", "表", "bi", "看板", "报表", "排名", "top", "bottom", "趋势", "销售", "订单", "客户", "渠道", "库存", "利润", "金额")):
            return IntentResult(intent="bi_create")
        if any(k in text for k in ("chart", "report", "dashboard", "rank", "sales", "trend", "top")):
            return IntentResult(intent="bi_create")
        return IntentResult(intent="non_bi")

    def _best_fields(self, message: str, context: BuilderContext) -> Tuple[Optional[Dict[str, Any]], str, str, Optional[str]]:
        best_profile = context.profiles[0] if context.profiles else None
        if not best_profile:
            return None, "", "", None
        for profile in context.profiles:
            if profile.get("sheet_name") and profile["sheet_name"] in message:
                best_profile = profile
                break
        fields = best_profile.get("fields", [])
        metrics = [f for f in fields if f.get("data_role") == "metric"]
        dims = [f for f in fields if f.get("data_role") == "dimension" and f.get("groupable")]
        times = [f for f in fields if f.get("data_role") == "time"]
        metric = self._field_by_message(message, metrics) or (metrics[0]["field"] if metrics else "*")
        dimension = self._field_by_message(message, dims) or (dims[0]["field"] if dims else "")
        time_field = self._field_by_message(message, times) or (times[0]["field"] if times else None)
        return best_profile, metric, dimension, time_field

    def _field_by_message(self, message: str, fields: List[Dict[str, Any]]) -> Optional[str]:
        for field in fields:
            name = field.get("field", "")
            if name and name in message:
                return name
        return None

    def _field_options(self, context: BuilderContext, role: str) -> List[Dict[str, Any]]:
        options = []
        seen = set()
        for profile in context.profiles:
            for field in profile.get("fields", []):
                if field.get("data_role") == role and field["field"] not in seen:
                    seen.add(field["field"])
                    options.append({
                        "label": field["field"],
                        "value": field["field"],
                        "description": profile.get("sheet_name", ""),
                    })
        return options or [{"label": "记录数", "value": "*"}]

    def _explore_directions(self, context: BuilderContext) -> List[Dict[str, Any]]:
        directions = []
        for profile in context.profiles[:3]:
            metrics = [f["field"] for f in profile.get("fields", []) if f.get("data_role") == "metric"]
            dims = [f["field"] for f in profile.get("fields", []) if f.get("data_role") == "dimension"]
            times = [f["field"] for f in profile.get("fields", []) if f.get("data_role") == "time"]
            metric = metrics[0] if metrics else "记录数"
            dim = dims[0] if dims else ""
            if dim:
                directions.append({"title": f"{profile['sheet_name']}：{dim}{metric}排名", "prompt": f"创建{dim}{metric}Top 5排名"})
            if times:
                directions.append({"title": f"{profile['sheet_name']}：{metric}趋势", "prompt": f"创建{metric}月度趋势"})
        return directions[:5] or [{"title": "数据总览", "prompt": "创建数据总览看板"}]

    def _recommended_categories(self, chart_list: List[Dict[str, Any]], context: BuilderContext) -> List[Dict[str, Any]]:
        out = []
        for chart in chart_list:
            category_id = chart.get("target_category_id")
            category = next((c for c in context.categories if c.get("id") == category_id), None)
            if category:
                out.append({"client_chart_id": chart.get("client_chart_id"), "category_id": category_id, "category_name": category.get("name") or category.get("display_name")})
        return out

    def _normalise_draft(
        self,
        draft: Dict[str, Any],
        context: BuilderContext,
        base_chart: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if base_chart and draft.get("source") in {None, "", "adjust_existing"}:
            merged = self._draft_from_existing(draft.get("title") or "", base_chart)
            merged.update({k: v for k, v in draft.items() if v not in (None, "")})
            return merged
        profile, metric, dimension, time_field = self._best_fields(draft.get("title") or "", context)
        if not profile:
            return draft
        normalised = dict(draft)
        normalised.setdefault("client_chart_id", f"draft_{uuid.uuid4().hex[:8]}")
        normalised.setdefault("source", "user_request")
        normalised.setdefault("title", "新建图表")
        normalised.setdefault("analysis_type", "ranking_top")
        normalised.setdefault("chart_type", "bar")
        normalised.setdefault("target_category_id", self._category_id_for(profile))
        normalised.setdefault("table_name", profile.get("table_name"))
        normalised.setdefault("metric", {"field": metric, "aggregation": "sum", "label": metric})
        normalised.setdefault("dimensions", [dimension] if dimension else [])
        normalised.setdefault("time_field", time_field)
        normalised.setdefault("filters", [])
        normalised.setdefault("required", True)
        normalised.setdefault("write_mode", "append")
        return normalised

    def _category_id_for(self, profile: Dict[str, Any]) -> str:
        return f"sheet_{profile.get('sheet_index', 0)}"

    def _compact_context(self, context: BuilderContext) -> Dict[str, Any]:
        return {
            "file_id": context.file_id,
            "space_id": context.space_id,
            "sheets": context.sheets,
            "profiles": [
                {
                    "sheet_name": p.get("sheet_name"),
                    "sheet_index": p.get("sheet_index"),
                    "table_name": p.get("table_name"),
                    "fields": [
                        {
                            "field": f.get("field"),
                            "data_role": f.get("data_role"),
                            "groupable": f.get("groupable"),
                            "sample_values": (f.get("sample_values") or [])[:8],
                        }
                        for f in p.get("fields", [])
                    ],
                }
                for p in context.profiles
            ],
            "categories": context.categories,
            "charts": [
                {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "chart_type": c.get("chart_type") or c.get("type"),
                    "category_id": c.get("category_id") or c.get("categoryId"),
                    "metric": c.get("metric"),
                    "dimensions": c.get("dimensions"),
                    "x_field": c.get("x_field"),
                    "y_field": c.get("y_field"),
                }
                for c in context.charts
            ],
            "business_knowledge": context.business_knowledge,
            "user_preferences": context.user_preferences,
        }

    def _compact_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": session.get("id"),
            "state": session.get("state"),
            "context_chart_id": session.get("context_chart_id"),
            "base_chart_id": session.get("base_chart_id"),
            "chart_list": session.get("chart_list") or [],
        }

    async def _safe_agent_call(self, func: Any, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            result = await asyncio.wait_for(func(payload), timeout=8.0)
            return result if isinstance(result, dict) else None
        except Exception:
            return None

    def _blocked_reply(self, context: BuilderContext) -> Optional[Dict[str, Any]]:
        if not context.sheets:
            return {
                "state": "blocked",
                "reply": {
                    "content": "当前还没有可用的数据表，先去数据页上传并完成分析。",
                    "blocks": [{"type": "actions", "items": [{"type": "navigate", "label": "去数据页", "target": "/data"}]}],
                },
            }
        return None

    def _default_reply(self) -> Dict[str, Any]:
        return {
            "state": "non_bi_answered",
            "reply": {
                "content": "我是 BI 报表构建助手，可以帮你基于当前数据创建、调整或查找 BI 报表。你可以告诉我想看什么指标、按什么维度分析，或者直接问这份数据能做什么分析。",
                "blocks": [],
            },
        }

    def _with_session(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload.setdefault("session_id", session_id)
        payload.setdefault("actions", [])
        return payload
