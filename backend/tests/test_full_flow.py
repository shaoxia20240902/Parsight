"""
完整流程测试脚本
测试上传、分析、深度调研、快速问答的完整流程
"""

import asyncio
import json
import httpx
from pathlib import Path
from datetime import datetime

# 测试配置
BASE_URL = "http://localhost:8000"
TEST_RESULTS_DIR = Path(__file__).parent.parent.parent / "test_results"
MOCK_DATA_DIR = Path(__file__).parent.parent.parent / "mock_data"


async def test_health():
    """测试健康检查接口"""
    print("\n=== 测试健康检查接口 ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/health")
        result = response.json()
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result


async def test_upload():
    """测试文件上传接口"""
    print("\n=== 测试文件上传接口 ===")

    # 查找Mock数据文件
    xlsx_files = list(MOCK_DATA_DIR.glob("*.xlsx"))
    if not xlsx_files:
        print("错误: 未找到Mock数据文件，请先运行 generate_mock_data.py")
        return None

    xlsx_file = xlsx_files[0]
    print(f"上传文件: {xlsx_file.name}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(xlsx_file, "rb") as f:
            files = {"file": (xlsx_file.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            response = await client.post(f"{BASE_URL}/api/upload", files=files)

        result = response.json()
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result


async def test_get_bi_config(file_id: str):
    """测试 BI 配置接口（上传后自动生成）"""
    print("\n=== 测试 BI 配置接口 ===")
    print(f"文件ID: {file_id}")

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/bi/config/{file_id}")
        result = response.json()
        print(f"状态码: {response.status_code}")
        print(f"响应 keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        return result


async def test_deep_research(file_id: str, question: str):
    """测试深度调研接口"""
    print("\n=== 测试深度调研接口 ===")
    print(f"文件ID: {file_id}")
    print(f"问题: {question}")

    events = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/chat/deep-research",
            json={"file_id": file_id, "question": question}
        ) as response:
            print(f"状态码: {response.status_code}")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event_data = json.loads(line[6:])
                    events.append(event_data)
                    step = event_data.get("step")
                    status = event_data.get("status")
                    message = event_data.get("message", "")
                    print(f"  [{step}] {status}: {message}")

    return events


async def test_quick_qa(file_id: str, question: str):
    """测试快速问答接口"""
    print("\n=== 测试快速问答接口 ===")
    print(f"文件ID: {file_id}")
    print(f"问题: {question}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/chat/quick-qa",
            json={"file_id": file_id, "question": question}
        )
        result = response.json()
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("XLSX to BI 智能看板 - 完整流程测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"服务地址: {BASE_URL}")

    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {
        "test_time": datetime.now().isoformat(),
        "tests": {}
    }

    # 1. 健康检查
    try:
        health_result = await test_health()
        all_results["tests"]["health"] = {"status": "success", "result": health_result}
    except Exception as e:
        print(f"健康检查失败: {e}")
        all_results["tests"]["health"] = {"status": "error", "error": str(e)}
        print("\n服务未启动，请先启动后端服务: python run.py")
        return

    # 2. 文件上传
    try:
        upload_result = await test_upload()
        all_results["tests"]["upload"] = {"status": "success", "result": upload_result}

        if not upload_result or upload_result.get("code") != 200:
            print("文件上传失败，终止测试")
            return

        file_id = upload_result["data"]["file_id"]
    except Exception as e:
        print(f"文件上传失败: {e}")
        all_results["tests"]["upload"] = {"status": "error", "error": str(e)}
        return

    # 3. BI 配置（上传后 run_post_upload_analysis 已生成）
    try:
        bi_result = await test_get_bi_config(file_id)
        all_results["tests"]["bi_config"] = {"status": "success", "result": bi_result}
    except Exception as e:
        print(f"BI 配置获取失败: {e}")
        all_results["tests"]["bi_config"] = {"status": "error", "error": str(e)}

    # 4. 深度调研
    try:
        deep_research_events = await test_deep_research(
            file_id,
            "华东地区销售情况怎么样？"
        )
        all_results["tests"]["deep_research"] = {"status": "success", "events": deep_research_events}
    except Exception as e:
        print(f"深度调研失败: {e}")
        all_results["tests"]["deep_research"] = {"status": "error", "error": str(e)}

    # 6. 快速问答
    try:
        quick_qa_result = await test_quick_qa(file_id, "上个月总销售额多少？")
        all_results["tests"]["quick_qa"] = {"status": "success", "result": quick_qa_result}
    except Exception as e:
        print(f"快速问答失败: {e}")
        all_results["tests"]["quick_qa"] = {"status": "error", "error": str(e)}

    # 保存测试结果
    result_file = TEST_RESULTS_DIR / "full_flow_test.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("测试完成！")
    print(f"测试结果已保存至: {result_file}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
