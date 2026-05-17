"""
分步组装 Sheet 分析蓝图：选角 → 场景 → 问题 → 审视，输出统一 JSON 结构。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.agents.bi_pipeline_agents import (
    BIScenarioAgent,
    BIScenarioQuestionAgent,
    BISheetRolePickerAgent,
    BIQuestionReviewAgent,
)
from app.services.bi_context import sheet_payload_for_llm
from app.services.bi_pipeline_logger import (
    BIPipelineRunContext,
    STEP_BLUEPRINT_COMPLETE,
    STEP_BLUEPRINT_FAILED,
    STEP_QUESTIONS,
    STEP_REVIEW,
    STEP_ROLE_PICKER,
    STEP_SCENARIOS,
    log_step_error,
    log_step_ok,
    log_step_warn,
)

logger = logging.getLogger(__name__)


class BIBlueprintPipeline:
    """多步蓝图流水线，最终结构与单步蓝图兼容。"""

    def __init__(self, concurrency: int = 3):
        self.role_agent = BISheetRolePickerAgent()
        self.scenario_agent = BIScenarioAgent()
        self.question_agent = BIScenarioQuestionAgent()
        self.review_agent = BIQuestionReviewAgent()
        self.sem = asyncio.Semaphore(concurrency)

    async def run(
        self,
        profile: Dict[str, Any],
        understanding_text: str,
        industry_guess: Dict[str, Any] | None = None,
        *,
        run_ctx: Optional[BIPipelineRunContext] = None,
    ) -> Dict[str, Any]:
        table_name = profile.get("table_name", "")
        sheet_name = profile.get("sheet_name", "")
        sheet_payload = sheet_payload_for_llm(profile, understanding_text, industry_guess)
        warnings: List[str] = []

        log_step_ok(
            STEP_ROLE_PICKER,
            "开始选角",
            run_ctx=run_ctx,
            table_name=table_name,
            sheet_name=sheet_name,
        )

        # Step 1: 业务一句话 + 选角
        try:
            role_result = await self.role_agent.run({"sheet_payload": sheet_payload})
        except Exception as e:
            log_step_error(
                STEP_ROLE_PICKER,
                "选角 LLM 调用失败",
                run_ctx=run_ctx,
                table_name=table_name,
                sheet_name=sheet_name,
                exc=e,
            )
            raise

        business_one_liner = role_result.get("business_one_liner", "")
        perspectives = role_result.get("perspectives", [])
        warnings.extend(role_result.get("warnings") or [])
        log_step_ok(
            STEP_ROLE_PICKER,
            f"选角完成，共 {len(perspectives)} 个角色",
            run_ctx=run_ctx,
            table_name=table_name,
            sheet_name=sheet_name,
            extra={
                "business_one_liner": business_one_liner,
                "perspective_ids": [p.get("perspective_id") for p in perspectives],
                "agent_warnings": role_result.get("warnings"),
            },
        )

        # Step 2: 每角色定场景（并行）
        async def build_scenarios(perspective: Dict[str, Any]) -> Dict[str, Any]:
            pid = perspective.get("perspective_id")
            rname = perspective.get("role_name")
            async with self.sem:
                payload = {
                    "sheet_payload": sheet_payload,
                    "perspective": perspective,
                }
                try:
                    scen_result = await self.scenario_agent.run({"perspective_payload": payload})
                    perspective["scenarios"] = scen_result.get("scenarios", [])
                    warnings.extend(scen_result.get("warnings") or [])
                    log_step_ok(
                        STEP_SCENARIOS,
                        f"场景生成成功，{len(perspective['scenarios'])} 个场景",
                        run_ctx=run_ctx,
                        table_name=table_name,
                        sheet_name=sheet_name,
                        perspective_id=pid,
                        role_name=rname,
                        extra={
                            "scenario_ids": [s.get("scenario_id") for s in perspective["scenarios"]],
                        },
                    )
                except Exception as e:
                    logger.warning("场景生成失败 %s: %s", pid, e)
                    perspective["scenarios"] = []
                    msg = f"角色 {rname} 场景生成失败: {e}"
                    warnings.append(msg)
                    log_step_warn(
                        STEP_SCENARIOS,
                        msg,
                        run_ctx=run_ctx,
                        table_name=table_name,
                        sheet_name=sheet_name,
                        perspective_id=pid,
                        role_name=rname,
                        exc=e,
                    )
                return perspective

        perspectives = await asyncio.gather(*[build_scenarios(p) for p in perspectives])

        # Step 3: 每场景定问题（并行）
        async def fill_questions(perspective: Dict[str, Any], scenario: Dict[str, Any]) -> None:
            pid = perspective.get("perspective_id")
            rname = perspective.get("role_name")
            sid = scenario.get("scenario_id")
            sname = scenario.get("scenario_name")
            async with self.sem:
                payload = {
                    "sheet_payload": sheet_payload,
                    "perspective": {
                        "perspective_id": pid,
                        "role_name": rname,
                        "role_background": perspective.get("role_background"),
                    },
                    "scenario": scenario,
                }
                try:
                    q_result = await self.question_agent.run({"scenario_payload": payload})
                    scenario["questions"] = q_result.get("questions", [])
                    warnings.extend(q_result.get("warnings") or [])
                    log_step_ok(
                        STEP_QUESTIONS,
                        f"问题生成成功，{len(scenario['questions'])} 道题",
                        run_ctx=run_ctx,
                        table_name=table_name,
                        sheet_name=sheet_name,
                        perspective_id=pid,
                        role_name=rname,
                        scenario_id=sid,
                        scenario_name=sname,
                        extra={
                            "question_ids": [q.get("question_id") for q in scenario["questions"]],
                        },
                    )
                except Exception as e:
                    logger.warning("问题生成失败 %s/%s: %s", pid, sid, e)
                    scenario["questions"] = []
                    msg = f"场景 {sname} 问题生成失败: {e}"
                    warnings.append(msg)
                    log_step_warn(
                        STEP_QUESTIONS,
                        msg,
                        run_ctx=run_ctx,
                        table_name=table_name,
                        sheet_name=sheet_name,
                        perspective_id=pid,
                        role_name=rname,
                        scenario_id=sid,
                        scenario_name=sname,
                        exc=e,
                    )

        question_tasks = []
        for perspective in perspectives:
            for scenario in perspective.get("scenarios", []):
                question_tasks.append(fill_questions(perspective, scenario))
        if question_tasks:
            await asyncio.gather(*question_tasks)

        # Step 4: 每角色审视补题
        for perspective in perspectives:
            pid = perspective.get("perspective_id")
            rname = perspective.get("role_name")
            review_payload = {
                "sheet_payload": sheet_payload,
                "perspective": perspective,
            }
            try:
                review = await self.review_agent.run({"perspective_payload": review_payload})
                added = len(review.get("additional_questions") or [])
                self._merge_review_questions(perspective, review)
                warnings.extend(review.get("gaps") or [])
                log_step_ok(
                    STEP_REVIEW,
                    f"审视完成，need_more={review.get('need_more_questions')}，补题 {added} 道",
                    run_ctx=run_ctx,
                    table_name=table_name,
                    sheet_name=sheet_name,
                    perspective_id=pid,
                    role_name=rname,
                    extra={
                        "coverage_ok": review.get("coverage_ok"),
                        "gaps": review.get("gaps"),
                    },
                )
            except Exception as e:
                logger.warning("审视失败 %s: %s", pid, e)
                msg = f"角色 {rname} 审视失败: {e}"
                warnings.append(msg)
                log_step_warn(
                    STEP_REVIEW,
                    msg,
                    run_ctx=run_ctx,
                    table_name=table_name,
                    sheet_name=sheet_name,
                    perspective_id=pid,
                    role_name=rname,
                    exc=e,
                )

        # 移除无问题的空场景
        for perspective in perspectives:
            perspective["scenarios"] = [
                s for s in perspective.get("scenarios", [])
                if s.get("questions")
            ]

        perspectives = [p for p in perspectives if p.get("scenarios")]

        if not perspectives:
            log_step_error(
                STEP_BLUEPRINT_FAILED,
                "蓝图流水线未生成任何有效场景与问题",
                run_ctx=run_ctx,
                table_name=table_name,
                sheet_name=sheet_name,
                extra={"warnings": warnings},
            )
            raise ValueError("蓝图流水线未生成任何有效场景与问题")

        log_step_ok(
            STEP_BLUEPRINT_COMPLETE,
            f"蓝图组装完成，{len(perspectives)} 个有效角色",
            run_ctx=run_ctx,
            table_name=table_name,
            sheet_name=sheet_name,
            extra={
                "warning_count": len(warnings),
                "role_count": len(perspectives),
            },
        )

        return {
            "business_one_liner": business_one_liner,
            "perspectives": list(perspectives),
            "warnings": warnings,
            "pipeline_steps": ["role_picker", "scenarios", "questions", "review"],
        }

    def _merge_review_questions(self, perspective: Dict[str, Any], review: Dict[str, Any]) -> None:
        if not review.get("need_more_questions"):
            return
        additional = review.get("additional_questions") or []
        if not additional:
            return
        supplement = next(
            (s for s in perspective.get("scenarios", []) if s.get("scenario_id") == "_supplement"),
            None,
        )
        if not supplement:
            supplement = {
                "scenario_id": "_supplement",
                "scenario_name": "补充分析",
                "scenario_context": "审视后补充的关键问题",
                "questions": [],
            }
            perspective.setdefault("scenarios", []).append(supplement)
        for aq in additional[:3]:
            aq = dict(aq)
            aq["from_review"] = True
            if not aq.get("scenario_id"):
                aq["scenario_id"] = "_supplement"
            target = next(
                (s for s in perspective["scenarios"] if s.get("scenario_id") == aq.get("scenario_id")),
                supplement,
            )
            target.setdefault("questions", []).append(aq)
