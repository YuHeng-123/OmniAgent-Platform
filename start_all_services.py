import os
import subprocess
import time
import socket

# 这里配置我们要统一启动的微服务矩阵
PROJECTS = [
    {"id": "ai-gateway", "name": "AI Gateway", "port": 8000, "path": "../ai-gateway"},
    {"id": "ecom-ai-guide", "name": "导购智能体", "port": 8001, "path": "../ecom-ai-guide"},
    # 接下来的项目后续也可以填进这里...
    # {"id": "graph_xiaohongshu", "name": "小红书运营", "port": 8502, "path": "../graph_xiaohongshu"}
]

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_service(project):
    print(f"[{project['name']}] 正在准备启动...")
    
    if is_port_in_use(project['port']):
        print(f"[{project['name']}] 端口 {project['port']} 已被占用，服务可能已经在运行中。跳过。\n")
        return None
        
    abs_path = os.path.abspath(project['path'])
    if not os.path.exists(abs_path):
        print(f"[错误] 找不到路径: {abs_path}\n")
        return None
        
    # 静默拉起子进程（不弹黑窗口，日志重定向到文件）
    log_path = os.path.abspath(f"logs/{project['id']}.log")
    os.makedirs("logs", exist_ok=True)
    
    with open(log_path, "a", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            ["cmd.exe", "/c", "run.bat"],
            cwd=abs_path,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    print(f"[{project['name']}] 启动指令已发送！(PID: {proc.pid})，日志路径: {log_path}\n")
    return proc

if __name__ == "__main__":
    print("===========================================")
    print("  OmniAgent Platform - 全域微服务一键启动")
    print("===========================================\n")
    
    processes = []
    for proj in PROJECTS:
        p = start_service(proj)
        if p:
            processes.append(p)
        time.sleep(2) # 错峰启动，避免并发 IO 冲突
        
    print("✅ [调度完成] 所有已配置的微服务已全部派发启动。")
    print("请前往大盘 (http://localhost:9999) 查看，或者按 Ctrl+C 退出主控。")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[退出] 收到退出信号，终止所有子服务...")
        for p in processes:
            p.kill()
        print("所有服务已关闭。")
