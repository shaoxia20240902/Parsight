from io import BytesIO
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.services.db_service import DBService

router = APIRouter(prefix="/api/data", tags=["data"])


# ========== 数据管理 ==========

@router.get("/tables")
async def get_tables(
    space_id: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取当前空间下所有动态表"""
    if not space_id:
        raise HTTPException(status_code=400, detail="需要提供 space_id")

    db_service = DBService(db)
    tables = await db_service.get_tables_by_space(space_id)

    return {
        "code": 200,
        "data": tables
    }


@router.get("/table/{table_name}/columns")
async def get_table_columns_endpoint(
    table_name: str,
    db: AsyncSession = Depends(get_db)
):
    """获取表的所有列信息"""
    db_service = DBService(db)
    columns = await db_service.get_table_columns(table_name)

    if not columns:
        raise HTTPException(status_code=404, detail=f"未找到表: {table_name}")

    # 获取行数
    row_count = await db_service.get_table_row_count(table_name)

    return {
        "code": 200,
        "data": {
            "table_name": table_name,
            "columns": columns,
            "row_count": row_count
        }
    }


@router.get("/table/{table_name}/rows")
async def get_table_rows(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: str = Query(""),
    search_field: str = Query(""),
    db: AsyncSession = Depends(get_db)
):
    """分页查询表数据 + 模糊搜索"""
    db_service = DBService(db)
    result = await db_service.paginated_query(
        table_name=table_name,
        page=page,
        page_size=page_size,
        search=search,
        search_field=search_field
    )

    return {
        "code": 200,
        "data": result
    }


@router.get("/export")
async def export_space_data(
    space_id: str = Query(..., description="空间 ID"),
    db: AsyncSession = Depends(get_db),
):
    """导出当前空间全部 Sheet 为 XLSX"""
    db_service = DBService(db)
    tables = await db_service.get_tables_by_space(space_id)
    if not tables:
        raise HTTPException(status_code=400, detail="当前空间暂无数据可导出")

    buffer = BytesIO()
    used_sheet_names: set[str] = set()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for table in tables:
            sheet_name = (table.get("sheet_name") or "Sheet")[:31]
            base_name = sheet_name
            suffix = 1
            while sheet_name in used_sheet_names:
                suffix += 1
                sheet_name = f"{base_name[:28]}_{suffix}"[:31]
            used_sheet_names.add(sheet_name)

            col_names = [c["name"] for c in (table.get("columns") or [])]
            rows = await db_service.fetch_all_table_rows(table["table_name"])
            if col_names:
                df = pd.DataFrame(rows, columns=col_names)
            else:
                df = pd.DataFrame(rows)
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    buffer.seek(0)
    filename = "export.xlsx"
    encoded = quote(filename)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
