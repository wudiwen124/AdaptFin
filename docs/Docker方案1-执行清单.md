# Docker 方案 1 执行清单（Docker Desktop + 数据目录放 D 盘）

> 状态：✅ **已完成并验证通过**（docker compose up --build 成功，http://localhost:8001/docs 可访问）。
> 关键坑：D:\ 根目录普通用户只读 → 数据目录用 D:\25328\DockerDesktopWSL；Docker Hub 拉取超时 → 配国内 registry-mirrors + Dockerfile 用清华 PyPI。
> 检测结论：Win11 家庭版、虚拟化已开、内存 15.7GB、D 盘空闲 66.5GB——满足条件；WSL2 未安装。

## 第一步：管理员 PowerShell 安装 WSL2（会重启）

1. 右键“开始” → “终端(管理员)” / “Windows PowerShell(管理员)”。
2. 执行：
   ```powershell
   wsl --install
   ```
3. **重启电脑**。

## 第二步：安装 Docker Desktop

重启后，管理员 PowerShell 执行：

```powershell
winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
```

或从官网 https://www.docker.com/products/docker-desktop/ 下载安装。

## 第三步：首次启动并确认 WSL2 后端

- 启动 Docker Desktop，等右下角状态变为 “Engine running”；
- 如提示需要 WSL2 内核更新，按提示安装并重启一次。

## 第四步：把数据目录改到 D 盘

1. 打开 Docker Desktop → **Settings（设置）** → **Resources（资源）** → **Advanced（高级）**；
2. 找到 **Disk image location（磁盘映像位置）**，改成 `D:\25328\DockerDesktopWSL`（该目录已创建且你有完全控制权）；
3. 点击 Apply & Restart。

> 不要填 `D:\Docker` 或 `D:\DockerDesktopWSL`（D 盘根目录对普通用户只读，会报 Access denied）。
> 改完后：镜像/容器/虚拟磁盘都存 D:\25328 下，C 盘仅保留程序本体约 4~6GB。

## 第五步：验证并启动本项目

管理员或普通 PowerShell（Docker 已随登录启动）执行：

```powershell
docker --version
docker compose version
cd E:\Codex\multi-agent
docker compose up --build
```

浏览器打开 http://localhost:8001/docs 验证接口可用；Ctrl+C 停止，`docker compose down` 清理。

## 预计空间

- C 盘：Docker Desktop 程序 + WSL 后端约 4~6GB；
- D 盘：项目镜像约 2~3GB + 虚拟磁盘增长空间（66.5GB 空闲，无压力）。
