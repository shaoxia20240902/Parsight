import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import load_only
from sqlalchemy.exc import IntegrityError
from app.models.database import get_db
from app.models.user import User
from app.models.file_record import FileRecord
from app.services.xlsx_parser import XlsxParser, build_table_name
from app.services.db_service import DBService
from app.utils.reimport_validator import validate_reimport_sheets
from app.services.bi_understanding_tasks import run_post_upload_understanding
from app.routers.auth import get_current_user
from app.config import UPLOAD_DIR, ALLOWED_EXTENSIONS, OSS_ENDPOINT, OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME, OSS_BASE_PATH

router = APIRouter(prefix="/api", tags=["upload"])

async def run_post_upload_analysis(
    db_service: DBService,
    file_id: str,
    sheets_info: list,
):
    """上传后：异步执行 Sheet 摘要 + 六维理解（不自动生成 BI）。"""
    await db_service.update_file_status(file_id, "uploaded")
    asyncio.create_task(run_post_upload_understanding(file_id, sheets_info))


async def upload_to_oss(file_path: Path, oss_path: str) -> bool:
    """上传文件到 OSS（如果配置了凭证）"""
    if not OSS_ENDPOINT or not OSS_ACCESS_KEY_ID:
        print(f"OSS 未配置，跳过上传: {oss_path}")
        return False
    try:
        import oss2
        auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
        bucket.put_object_from_file(oss_path, str(file_path))
        print(f"OSS 上传成功: {oss_path}")
        return True
    except ImportError:
        print("oss2 库未安装，跳过 OSS 上传")
        return False
    except Exception as e:
        print(f"OSS 上传失败: {e}")
        return False


async def resolve_space_seq_id(
    db_service: DBService,
    space_id: Optional[str],
    owner_id: str,
) -> int:
    if not space_id:
        raise HTTPException(status_code=400, detail="请先选择空间后再上传")
    seq_id = await db_service.get_space_seq_id_for_user(space_id, owner_id)
    if seq_id is None:
        raise HTTPException(status_code=404, detail="空间不存在或无权访问")
    return seq_id


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    space_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传XLSX文件"""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_ext}，仅支持 .xlsx/.xls")

    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}{file_ext}"

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        parse_result = XlsxParser.parse_file(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    db_service = DBService(db)
    space_seq_id = await resolve_space_seq_id(db_service, space_id, current_user.id)
    file_record = await db_service.create_file_record(file.filename, len(parse_result["sheets"]), space_id)

    username = current_user.username
    sheets_info = []
    for sheet in parse_result["sheets"]:
        table_name = build_table_name(username, space_seq_id, sheet["name"])

        base_table_name = table_name
        suffix = 1
        while True:
            try:
                await db_service.create_sheet_meta(file_record.id, {
                    "index": sheet["index"],
                    "name": sheet["name"],
                    "columns": sheet["columns"],
                    "row_count": sheet["row_count"],
                    "table_name": table_name
                })
                break
            except IntegrityError:
                await db.rollback()
                suffix += 1
                table_name = f"{base_table_name}_{suffix}"

        create_sql = XlsxParser.create_table_sql(table_name, sheet["columns"])
        await db_service.create_dynamic_table(table_name, create_sql)

        insert_sql, values = XlsxParser.insert_data_sql(table_name, sheet["data"])
        await db_service.insert_data(insert_sql, values)

        sheets_info.append({
            "index": sheet["index"],
            "name": sheet["name"],
            "columns": [col["name"] for col in sheet["columns"]],
            "row_count": sheet["row_count"],
            "table_name": table_name
        })

    oss_path = f"{OSS_BASE_PATH}/{username}/{space_seq_id}/{file_id}.xlsx"
    await upload_to_oss(file_path, oss_path)

    await run_post_upload_analysis(db_service, file_record.id, sheets_info)

    return {
        "code": 200,
        "data": {
            "file_id": file_record.id,
            "filename": file.filename,
            "sheet_count": len(sheets_info),
            "space_seq_id": space_seq_id,
            "sheets": sheets_info
        }
    }


@router.post("/upload/stream")
async def upload_file_stream(
    file: UploadFile = File(...),
    space_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传XLSX文件 - SSE 流式返回进度事件"""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_ext}，仅支持 .xlsx/.xls")

    db_service = DBService(db)
    space_seq_id = await resolve_space_seq_id(db_service, space_id, current_user.id)

    async def event_stream():
        try:
            yield f"data: {json.dumps({'step': 'saving', 'status': 'processing', 'message': '正在保存文件...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            file_id = str(uuid.uuid4())
            file_path = UPLOAD_DIR / f"{file_id}{file_ext}"
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            yield f"data: {json.dumps({'step': 'saving', 'status': 'completed', 'message': '文件已保存'}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'step': 'parsing', 'status': 'processing', 'message': '正在解析文件结构...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            try:
                parse_result = XlsxParser.parse_file(file_path)
            except Exception as e:
                yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': f'文件解析失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                return

            sheet_count = len(parse_result["sheets"])
            yield f"data: {json.dumps({'step': 'parsing', 'status': 'completed', 'message': f'解析完成，共 {sheet_count} 个Sheet'}, ensure_ascii=False)}\n\n"

            file_record = await db_service.create_file_record(file.filename, sheet_count, space_id)
            username = current_user.username

            yield f"data: {json.dumps({'step': 'creating_tables', 'status': 'processing', 'message': '正在创建数据表...', 'progress': 0, 'total': sheet_count}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

            sheets_info = []
            for i, sheet in enumerate(parse_result["sheets"]):
                progress_pct = int((i / sheet_count) * 100)
                s_name = sheet["name"]
                yield f"data: {json.dumps({'step': 'creating_tables', 'status': 'processing', 'message': f'正在处理: {s_name}', 'progress': progress_pct, 'total': sheet_count}, ensure_ascii=False)}\n\n"

                table_name = build_table_name(username, space_seq_id, s_name)

                base_table_name = table_name
                suffix = 1
                while True:
                    try:
                        await db_service.create_sheet_meta(file_record.id, {
                            "index": sheet["index"],
                            "name": sheet["name"],
                            "columns": sheet["columns"],
                            "row_count": sheet["row_count"],
                            "table_name": table_name
                        })
                        break
                    except IntegrityError:
                        await db.rollback()
                        suffix += 1
                        table_name = f"{base_table_name}_{suffix}"

                create_sql = XlsxParser.create_table_sql(table_name, sheet["columns"])
                await db_service.create_dynamic_table(table_name, create_sql)

                s_row_count = sheet["row_count"]
                yield f"data: {json.dumps({'step': 'inserting_data', 'status': 'processing', 'message': f'正在导入数据: {s_name} ({s_row_count} 行)', 'progress': progress_pct, 'total': sheet_count}, ensure_ascii=False)}\n\n"

                insert_sql, values = XlsxParser.insert_data_sql(table_name, sheet["data"])
                await db_service.insert_data(insert_sql, values)

                sheets_info.append({
                    "index": sheet["index"],
                    "name": sheet["name"],
                    "columns": [col["name"] for col in sheet["columns"]],
                    "row_count": sheet["row_count"],
                    "table_name": table_name
                })

            yield f"data: {json.dumps({'step': 'analyzing', 'status': 'processing', 'message': '正在调用 AI 分析数据...', 'progress': 90, 'total': sheet_count}, ensure_ascii=False)}\n\n"

            await run_post_upload_analysis(db_service, file_record.id, sheets_info)

            oss_path = f"{OSS_BASE_PATH}/{username}/{space_seq_id}/{file_id}.xlsx"
            await upload_to_oss(file_path, oss_path)

            yield f"data: {json.dumps({'step': 'done', 'status': 'completed', 'message': '导入完成', 'progress': 100, 'total': sheet_count, 'data': {'file_id': file_record.id, 'filename': file.filename, 'sheet_count': len(sheets_info), 'sheets': sheets_info}}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/upload/validate-reimport")
async def validate_reimport(
    file: UploadFile = File(...),
    space_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """校验更新文件：Sheet 与字段名须与当前空间一致"""
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_ext}，仅支持 .xlsx/.xls")

    db_service = DBService(db)
    await resolve_space_seq_id(db_service, space_id, current_user.id)

    file_record = await db_service.get_latest_file_record(space_id)
    if not file_record:
        raise HTTPException(status_code=400, detail="当前空间尚无数据，请先上传文件")

    existing_tables = await db_service.get_tables_by_space(space_id)
    file_tables = [t for t in existing_tables if t.get("file_id") == file_record["id"]]
    if not file_tables:
        file_tables = existing_tables

    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"validate_{file_id}{file_ext}"
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        parse_result = XlsxParser.parse_file(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
    finally:
        if file_path.exists():
            file_path.unlink()

    validation = validate_reimport_sheets(file_tables, parse_result["sheets"])
    return {
        "code": 200,
        "data": {
            **validation,
            "filename": file.filename,
            "sheet_count": len(parse_result["sheets"]),
        },
    }


@router.post("/upload/reimport/stream")
async def reimport_file_stream(
    file: UploadFile = File(...),
    space_id: str = Form(...),
    mode: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新导入：覆盖（清空后写入）或插入（追加行）。
    不自动重新生成表理解，由前端弹窗引导用户选择。
    """
    if mode not in ("overwrite", "insert"):
        raise HTTPException(status_code=400, detail="mode 须为 overwrite 或 insert")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_ext}，仅支持 .xlsx/.xls")

    db_service = DBService(db)
    await resolve_space_seq_id(db_service, space_id, current_user.id)

    file_record = await db_service.get_latest_file_record(space_id)
    if not file_record:
        raise HTTPException(status_code=400, detail="当前空间尚无数据，请先上传文件")

    existing_tables = await db_service.get_tables_by_space(space_id)
    file_tables = [t for t in existing_tables if t.get("file_id") == file_record["id"]]
    if not file_tables:
        file_tables = existing_tables

    async def event_stream():
        file_path = None
        try:
            yield f"data: {json.dumps({'step': 'saving', 'status': 'processing', 'message': '正在保存文件...'}, ensure_ascii=False)}\n\n"

            temp_id = str(uuid.uuid4())
            file_path = UPLOAD_DIR / f"reimport_{temp_id}{file_ext}"
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            yield f"data: {json.dumps({'step': 'parsing', 'status': 'processing', 'message': '正在解析文件...'}, ensure_ascii=False)}\n\n"

            try:
                parse_result = XlsxParser.parse_file(file_path)
            except Exception as e:
                yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': f'文件解析失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                return

            validation = validate_reimport_sheets(file_tables, parse_result["sheets"])
            if not validation["valid"]:
                issues = validation.get("issues", [])
                msg = issues[0]["message"] if issues else "字段校验未通过"
                yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': msg, 'validation': validation}, ensure_ascii=False)}\n\n"
                return

            new_by_name = {s["name"]: s for s in parse_result["sheets"]}
            table_by_sheet = {t["sheet_name"]: t for t in file_tables}
            sheet_count = len(file_tables)
            mode_label = "全量覆盖" if mode == "overwrite" else "全量插入"

            yield f"data: {json.dumps({'step': 'importing', 'status': 'processing', 'message': f'开始{mode_label}...', 'progress': 0, 'total': sheet_count}, ensure_ascii=False)}\n\n"

            updated_tables = []
            for i, (sheet_name, table) in enumerate(table_by_sheet.items()):
                sheet = new_by_name[sheet_name]
                table_name = table["table_name"]
                progress_pct = int((i / sheet_count) * 100)

                if mode == "overwrite":
                    await db_service.clear_table_data(table_name)

                insert_sql, values = XlsxParser.insert_data_sql(table_name, sheet["data"])
                await db_service.insert_data(insert_sql, values)

                if mode == "overwrite":
                    new_row_count = sheet["row_count"]
                else:
                    new_row_count = await db_service.get_table_row_count(table_name)

                await db_service.update_sheet_row_count(table_name, new_row_count)

                updated_tables.append({
                    "table_name": table_name,
                    "sheet_name": sheet_name,
                    "row_count": new_row_count,
                })

                yield f"data: {json.dumps({'step': 'importing', 'status': 'processing', 'message': f'已处理: {sheet_name} ({new_row_count} 行)', 'progress': progress_pct, 'total': sheet_count}, ensure_ascii=False)}\n\n"

            await db_service.update_file_filename(file_record["id"], file.filename)

            yield f"data: {json.dumps({'step': 'done', 'status': 'completed', 'message': '更新完成', 'progress': 100, 'total': sheet_count, 'data': {'mode': mode, 'filename': file.filename, 'tables': updated_tables, 'warnings': validation.get('warnings', [])}}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'step': 'error', 'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            if file_path and file_path.exists():
                file_path.unlink()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/files")
async def list_files(
    space_id: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取文件列表（可按空间过滤）"""
    query = select(FileRecord).options(
        load_only(FileRecord.id, FileRecord.filename, FileRecord.upload_time,
                  FileRecord.sheet_count, FileRecord.status, FileRecord.space_id)
    ).order_by(FileRecord.upload_time.desc())
    if space_id:
        query = query.where(FileRecord.space_id == space_id)
    result = await db.execute(query)
    files = result.scalars().all()
    return {
        "code": 200,
        "data": [
            {
                "id": f.id,
                "filename": f.filename,
                "upload_time": f.upload_time.isoformat() if f.upload_time else "",
                "sheet_count": f.sheet_count,
                "status": f.status,
                "space_id": f.space_id
            }
            for f in files
        ]
    }
