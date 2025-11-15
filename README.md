# EMinder ✨

<div align="center">

*A flexible, template-driven email scheduling and sending toolkit.*  
*一个灵活的、模板驱动的邮件定时发送工具包。*

</div>

<p align="center">
  <a href="#english">English</a> •
  <a href="#中文">中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/Framework-FastAPI-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/UI-Gradio-orange.svg" alt="Gradio">
  <img src="https://img.shields.io/badge/Database-SQLite-blue.svg" alt="SQLite">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
</p>

---

<a name="english"></a>

## 🇬🇧 English

<details>
<summary><strong>Table of Contents</strong></summary>

- [EMinder ✨](#eminder-)
  - [🇬🇧 English](#-english)
    - [About The Project](#about-the-project)
    - [Key Features](#key-features)
    - [Tech Stack](#tech-stack)
    - [Project Structure](#project-structure)
    - [Getting Started](#getting-started)
      - [Prerequisites](#prerequisites)
      - [Installation \& Setup](#installation--setup)
    - [Usage](#usage)
    - [How to Customize a New Template](#how-to-customize-a-new-template)
    - [Roadmap](#roadmap)
    - [Contributing](#contributing)
    - [License](#license)
  - [🇨🇳 中文](#-中文)
    - [关于项目](#关于项目)
    - [核心功能](#核心功能)
    - [技术栈](#技术栈)
    - [项目结构](#项目结构)
    - [开始使用](#开始使用)
      - [先决条件](#先决条件)
      - [安装与配置](#安装与配置)
    - [如何使用](#如何使用)
    - [如何自定义一个新模板](#如何自定义一个新模板)
    - [未来蓝图 (TODO)](#未来蓝图-todo)
    - [如何贡献](#如何贡献)
    - [许可证](#许可证)

</details>

### About The Project

**EMinder** is a powerful tool designed to automate sending personalized and templated emails. Whether you need to send daily work summaries, weekly project reports, or custom motivational quotes, EMinder provides a flexible and extensible solution.

The project features a decoupled architecture with a **FastAPI** backend for robust API services and a **Gradio** frontend for an intuitive web-based control panel. It now uses **SQLite** to persist subscriber data and scheduled jobs, ensuring no data is lost upon restart.

### Key Features

-   📧 **Dynamic Templates**: The UI is dynamically generated based on template metadata. Adding new email templates is as simple as creating a Python file—no frontend code changes required!
-   💾 **Persistent Storage**: Uses SQLite to store subscriber lists and scheduled tasks, ensuring data durability across application restarts.
-   ⏰ **Flexible Scheduling**: Supports both recurring tasks (via Cron expressions) and one-off scheduled emails for a specific future time.
-   🖥️ **Interactive Web UI**: A user-friendly Gradio control panel to manage subscribers (Add, Edit, Delete), send emails manually, schedule tasks, and view/cancel all pending jobs.
-   🔧 **Decoupled & Scalable**: A clean separation between the FastAPI backend and the Gradio frontend makes the project easy to maintain and scale.
-   📤 **Multi-Source Senders**: Configure and use multiple sender email accounts. The system will rotate through them for sending.
-   🚫 **Pydantic-Free**: Built entirely without the `pydantic` library.

### Tech Stack

-   **Backend**: Python, FastAPI, Uvicorn, APScheduler
-   **Frontend**: Gradio
-   **Database**: SQLite (for subscribers and job persistence)
-   **Dependencies**: python-dotenv, requests, pytz, sqlalchemy

### Project Structure

```
EMinder/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints (subscribers, templates, jobs)
│   │   ├── core/             # Configuration management (config.py)
│   │   ├── services/         # Business logic (email, scheduling)
│   │   ├── storage/          # Data storage (sqlite_store.py)
│   │   ├── templates/        # Email template definitions
│   │   │   ├── email_templates.py    # Main template manager
│   │   │   └── customize_templates.py  # User-defined custom templates
│   │   └── main.py           # FastAPI application entry point
│   ├── run.py                # Script to run the backend
│   └── .env                  # Environment variables (!!! IMPORTANT !!!)
├── frontend.py               # Gradio web UI application
├── scripts/                  # Deployment scripts (systemd, etc.)
└── requirements.txt          # Python dependencies
```

### Getting Started

Follow these steps to get a local copy up and running.

#### Prerequisites

- **Git**: To clone the repository.
- **Conda / Miniconda**: To manage the Python environment.
- **Python 3.9** or newer.

#### Installation & Setup

1.  **Clone the repository**
    ```sh
    git clone https://github.com/your_username/EMinder.git
    cd EMinder
    ```

2.  **Create and activate the Conda environment**
    ```sh
    # Create an environment named 'eminder_env' with Python 3.9
    conda create --name eminder_env python=3.9 -y

    # Activate the environment
    conda activate eminder_env
    ```

3.  **Install dependencies**
    ```sh
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**
    -   Navigate to the `backend/` directory.
    -   Create a file named `.env` from `.env.example` or from scratch.
    -   Open `.env` and fill in your details. **This step is crucial.**

    ```ini
    # backend/.env

    # --- SMTP Server Configuration ---
    # Format: email1|app_password1,email2|app_password2
    SENDER_ACCOUNTS="your_email@example.com|your_app_specific_password"

    SMTP_SERVER="smtp.example.com"
    SMTP_PORT=465

    # --- Application Configuration ---
    APP_BASE_URL="http://127.0.0.1:8000"
    
    # --- Database Configuration ---
    # The database file will be created relative to the `backend` directory.
    DATABASE_URL="sqlite:///./eminder.db"

    # --- Scheduler Configuration ---
    # Cron expression for daily recurring emails (minute hour day month year)
    DAILY_SUMMARY_CRON="0 8 * * *" # Daily at 8:00 AM
    ```

5.  **Run the Application**
    -   **Start the Backend**:
        ```sh
        # From the project root, run:
        cd backend
        python run.py
        # Or for development with auto-reload:
        # uvicorn app.main:app --reload
        ```
    -   **Start the Frontend** (in a **second** terminal):
        ```sh
        # From the project root, run:
        python frontend.py
        ```

### Usage

Once both services are running, open your web browser and navigate to:

**`http://127.0.0.1:7860`**

You will see the EMinder Control Center with four tabs:
1.  **Subscription Management**: Add, view, edit, and delete subscribers.
2.  **Manual Send**: Immediately send a templated email. The form fields are built dynamically based on your chosen template.
3.  **Scheduled One-off Task**: Schedule an email to be sent at a specific future date and time.
4.  **Scheduled Jobs Management**: View all pending tasks (both one-off and recurring). You can cancel any task by its ID.

### How to Customize a New Template

Adding your own email template is incredibly simple and requires **no changes to the frontend code**.

1.  **Open the Custom Template File**: Navigate to `backend/app/templates/customize_templates.py`. This file is designed as a starting point for your own creations.

2.  **Define Metadata**: Create a dictionary that describes your template. This tells the UI what fields to show.
    -   `display_name`: The name shown in the dropdown menu.
    -   `description`: A short explanation of the template's purpose.
    -   `fields`: A list of input fields, where each field is a dictionary containing `name` (internal variable), `label` (UI display text), `type` (`text`, `textarea`, or `number`), and `default` value.

3.  **Write the Template Function**: Create a Python function that takes a dictionary (`data`) of the user's input and returns a dictionary with the email's `subject` and `content` (HTML).

4.  **Register Your Template**: Add your new template's metadata and function to the `custom_templates` dictionary at the bottom of the file.

5.  **Enable Your Template**: In `backend/app/templates/email_templates.py`, uncomment the following line at the top of the file:
    ```python
    from .customize_templates import custom_templates
    ```

6.  **Restart the Backend**: Rerun the backend server. Your new template will now automatically appear in the UI, ready to use!

### Roadmap

-   [ ] **Dynamic Data Sources**: Fetch user-specific data from an external API or database before sending an email.
-   [ ] **User Authentication**: Add a login system to protect the control panel.
-   [ ] **Containerization**: Provide `Dockerfile` and `docker-compose.yml` for easy deployment.
-   [ ] **Comprehensive Testing**: Add unit and integration tests for the backend services.

### Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

Please also feel free to open an issue for any bugs or feature requests.

### License

Distributed under the MIT License. See `LICENSE` file for more information.

---

<a name="中文"></a>

## 🇨🇳 中文

<details>
<summary><strong>目录</strong></summary>

- [关于项目](#关于项目)
- [核心功能](#核心功能)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [开始使用](#开始使用)
  - [先决条件](#先决条件)
  - [安装与配置](#安装与配置)
- [如何使用](#如何使用)
- [未来蓝图 (TODO)](#未来蓝图-todo)
- [如何贡献](#如何贡献)
- [许可证](#许可证)

</details>

### 关于项目

**EMinder** 是一款强大的工具，旨在自动化发送个性化的、基于模板的电子邮件。无论您需要发送每日工作总结、每周项目报告、像游戏一样的人生总结，还是自定义的激励名言，EMinder 都提供了一个灵活且可扩展的解决方案。

项目采用前后端分离架构，后端使用 **FastAPI** 提供稳健的 API 服务，前端则使用 **Gradio** 构建了一个直观、可交互的 Web 控制面板。这使您能够轻松地管理订阅和触发邮件任务。使用 **SQLite** 来持久化存储订阅者数据和计划任务，确保在服务重启后数据不会丢失。

### 核心功能

-   📧 **动态模板**: UI界面完全根据模板的元数据动态生成。添加新邮件模板就像创建一个Python文件一样简单——无需修改任何前端代码！
-   💾 **持久化存储**: 使用 SQLite 存储订阅者列表和已计划的任务，确保了在应用重启之间的数据持久性。
-   ⏰ **灵活调度**: 同时支持周期性任务（通过 Cron 表达式）和为未来特定时间点安排的一次性邮件。
-   🖥️ **交互式 Web UI**: 一个用户友好的 Gradio 控制面板，用于管理订阅者（增、删、改、查）、手动发送邮件、安排任务，以及查看/取消所有待处理的任务。
-   🔧 **解耦与可扩展**: FastAPI 后端和 Gradio 前端清晰分离，使得项目易于维护和扩展。
-   📤 **多源发信**: 支持配置和使用多个发件人邮箱账户，系统会在发送时进行轮换。
-   🚫 **无 Pydantic 依赖**: 项目完全不使用 `pydantic` 库进行构建。

### 技术栈

-   **后端**: Python, FastAPI, Uvicorn, APScheduler
-   **前端**: Gradio
-   **数据库**: SQLite (用于订阅者和任务持久化)
-   **依赖库**: python-dotenv, requests, pytz, sqlalchemy

### 项目结构

项目遵循模块化的结构，以实现更好的组织和可维护性。

```
EMinder/
├── backend/
│   ├── app/
│   │   ├── api/              # API 端点 (订阅者、模板、任务)
│   │   ├── core/             # 配置管理 (config.py)
│   │   ├── services/         # 业务逻辑 (邮件、调度)
│   │   ├── storage/          # 数据存储 (sqlite_store.py)
│   │   ├── templates/        # 邮件模板定义
│   │   │   ├── email_templates.py    # 主模板管理器
│   │   │   └── customize_templates.py  # 用户自定义模板
│   │   └── main.py           # FastAPI 应用入口
│   ├── run.py                # 运行后端的脚本
│   └── .env                  # 环境变量文件 (!!! 非常重要 !!!)
├── frontend.py               # Gradio Web UI 应用
└── requirements.txt          # Python 依赖
```

### 开始使用

按照以下步骤在您的本地环境中部署和运行项目。

#### 先决条件

-   **Git**: 用于克隆本仓库。
-   **Conda / Miniconda**: 用于管理 Python 环境。
-   **Python 3.9** 或更高版本。

#### 安装与配置

1.  **克隆仓库**
    ```sh
    git clone https://github.com/your_username/EMinder.git
    cd EMinder
    ```

2.  **创建并激活 Conda 环境**
    ```sh
    # 创建一个名为 eminder_env，使用 Python 3.9 的环境
    conda create --name eminder_env python=3.9 -y

    # 激活环境
    conda activate eminder_env
    ```

3.  **安装依赖**
    ```sh
    pip install -r requirements.txt
    ```

4.  **配置环境变量**
    -   进入 `backend/` 目录。
    -   根据 `.env.example` 创建一个 `.env` 文件。
    -   打开 `.env` 文件并填入您的信息。**此步骤至关重要。**

    ```ini
    # backend/.env

    # --- SMTP 服务器配置 ---
    # 格式: 邮箱1|授权码1,邮箱2|授权码2
    # 请使用您邮箱服务商提供的“应用专用授权码”，而不是您的登录密码！
    SENDER_ACCOUNTS="your_email@example.com|your_app_specific_password"

    SMTP_SERVER="smtp.example.com"
    SMTP_PORT=465

    # --- 应用配置 ---
    APP_BASE_URL="http://127.0.0.1:8000"

    # --- 数据库配置 ---
    # 数据库文件将创建在 `backend` 目录下
    DATABASE_URL="sqlite:///./eminder.db"

    # --- 调度器配置 ---
    # 用于每日周期性邮件的 Cron 表达式 (分 时 日 月 周)
    DAILY_SUMMARY_CRON="0 8 * * *" # 每天早上 8:00
    ```

5.  **运行应用**
    -   **启动后端**:
        ```sh
        # 在项目根目录执行
        cd backend
        python run.py
        # 或使用开发模式启动 (代码变动后自动重载)
        # uvicorn app.main:app --reload
        ```
    -   **启动前端** (在 **第二个** 终端中):
        ```sh
        # 在项目根目录执行
        python frontend.py
        ```

### 如何使用

当两个服务都成功运行后，打开您的浏览器并访问：

**`http://127.0.0.1:7860`**

您将看到 EMinder 控制中心，它包含四个选项卡：
1.  **订阅管理**: 添加、查看、编辑和删除订阅者。
2.  **手动发送**: 立即发送一封模板邮件。表单中的字段会根据您选择的模板动态生成。
3.  **定时单次任务**: 安排一封邮件，在未来的某个特定日期和时间发送。
4.  **计划任务管理**: 查看所有待处理的任务（包括一次性和周期性）。您可以根据任务ID取消任何一个任务。

### 如何自定义一个新模板

添加您自己的邮件模板非常简单，并且**无需修改任何前端代码**。

1.  **打开自定义模板文件**: 导航到 `backend/app/templates/customize_templates.py`。这个文件是为您创建自定义模板而设计的起点。

2.  **定义元数据**: 创建一个字典来描述您的模板，它会告诉UI界面需要显示哪些输入框。
    -   `display_name`: 在下拉菜单中显示的名称。
    -   `description`: 关于模板用途的简短描述。
    -   `fields`: 一个输入字段列表，每个字段都是一个字典，包含 `name` (内部变量名)、`label` (UI显示的标签)、`type` (`text`、`textarea` 或 `number`) 和 `default` (默认值)。

3.  **编写模板函数**: 创建一个Python函数，它接收一个包含用户输入的字典 (`data`)，并返回一个包含邮件 `subject` (主题) 和 `content` (HTML内容) 的字典。

4.  **注册你的模板**: 将您新创建的模板元数据和函数添加到文件底部的 `custom_templates` 字典中。

5.  **启用你的模板**: 在 `backend/app/templates/email_templates.py` 文件中，取消文件顶部以下这行代码的注释：
    ```python
    from .customize_templates import custom_templates
    ```

6.  **重启后端服务**: 重新运行后端服务。您的新模板现在会自动出现在UI界面中，立即可用！

### 未来蓝图 (TODO)

-   [ ] **动态数据源**: 在发送邮件前，从外部 API 或数据库中获取用户专属数据。
-   [ ] **用户认证**: 为控制面板添加登录系统以保护其安全。
-   [ ] **容器化**: 提供 `Dockerfile` 和 `docker-compose.yml` 文件，以便通过 Docker 轻松部署。
-   [ ] **全面的测试**: 为后端服务添加单元测试和集成测试。

### 如何贡献

我们欢迎任何形式的贡献，无论是报告 BUG、提出新功能建议，还是提交代码。您的每一次贡献都将使这个社区变得更加美好。

1.  Fork 本项目
2.  创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3.  提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4.  将分支推送到您的 Fork (`git push origin feature/AmazingFeature`)
5.  创建一个 Pull Request

### 许可证

本项目采用 MIT 许可证。详情请参阅 `LICENSE` 文件。