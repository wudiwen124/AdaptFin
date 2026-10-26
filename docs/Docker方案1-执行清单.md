# Windows 下安装和启动 Docker

这份记录对应本机使用 Docker Desktop 和 WSL2 后端的安装过程。项目镜像已经实际构建并启动，`http://localhost:8001/docs` 可以访问。

## 安装前检查

本机环境为 Windows 11 家庭版，已开启虚拟化，内存约 16 GB，D 盘有足够空间。安装 Docker Desktop 前需要确认 WSL2 可用。

## 1. 安装 WSL2

以管理员身份打开 PowerShell：

```powershell
wsl --install
```

安装完成后重启电脑。若系统提示更新 WSL 内核，按提示安装后再次重启。

## 2. 安装 Docker Desktop

可以使用 winget：

```powershell
winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
```

也可以从 Docker 官网下载安装包。首次启动后等待引擎状态变为运行中。

## 3. 修改镜像数据目录

默认数据放在 C 盘。为了给系统盘留空间，可以打开 Docker Desktop 的 `Settings -> Resources -> Advanced`，将磁盘映像位置改为非系统盘目录。

本机第一次填写 `D:\DockerDesktopWSL` 时出现 `Access is denied`。原因是 D 盘根目录对普通用户没有写权限，不是 Docker 本身的问题。后来使用已有写权限的目录：

```text
D:\25328\DockerDesktopWSL
```

设置完成后点击 `Apply & restart`。

## 4. 处理镜像拉取超时

首次构建时，Docker Hub token 请求和基础镜像拉取可能超时。本机为 Docker Desktop 配置了可用的 registry mirror，Dockerfile 中安装 Python 依赖时使用清华 PyPI 镜像。

镜像源只影响构建阶段。项目运行时仍按 `.env` 中配置的模型服务地址访问。

## 5. 启动项目

确认 `.env` 存在并已填写所需配置：

```powershell
docker --version
docker compose version
docker compose up --build
```

服务启动后访问：

```text
http://localhost:8001/docs
```

停止并删除当前容器：

```powershell
docker compose down
```

容器中的 `/app/data` 映射到项目目录的 `./data`。执行 `docker compose down` 不会删除本地数据库，但 `docker compose down -v` 会删除 Compose 管理的卷，使用时需要确认。

## 本机空间占用

Docker Desktop 程序、WSL 组件和镜像会占用数 GB。具体大小取决于基础镜像、Docker Desktop 版本和后续拉取的镜像，不建议按固定数字预估。该项目的数据目录会随用户数据和评测产物增加，主要占用空间的是数据库和 Docker 虚拟磁盘。
