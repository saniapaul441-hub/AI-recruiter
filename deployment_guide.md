# AI Recruiter - Deployment Guide

This guide describes how to deploy the AI Recruiter Python FastAPI web application (including the web dashboard and candidate screening portal) to cloud hosting providers.

---

## 🔑 Required Environment Variables
Regardless of the platform, you must configure the following environment variables in the settings/environment dashboard of your hosting provider:

| Variable Name | Type | Description |
|---|---|---|
| `GEMINI_API_KEY` | **Required** | Google Gemini API key (from [Google AI Studio](https://aistudio.google.com/)) used for resume parsing and interviews. |
| `SECRET_KEY` | **Required** | A long, secure random string used to sign JWT authentication tokens (e.g. `openssl rand -hex 32` or any random password). |
| `DATABASE_URL` | *Optional* | A SQL database URL. Defaults to local SQLite (`sqlite:///./recruiter.db`). **Note:** To keep data permanently (recruiter logins, job descriptions, screening configurations), you should hook up a PostgreSQL database. |
| `PINECONE_API_KEY` | *Optional* | If provided, enables cloud vector search. If left blank, the app falls back to local NumPy vector matching. |
| `PINECONE_ENV` | *Optional* | Pinecone region (e.g. `us-east-1`). |
| `PINECONE_INDEX` | *Optional* | Pinecone index name (defaults to `recruiter-fingerprints`). |

---

## ⚡ Option A: Hugging Face Spaces (Recommended - 100% Free, High Resource Tier)
Hugging Face Spaces offers a completely free CPU Basic tier with **16GB RAM and 2 vCPUs**. This is the best free option since it has plenty of memory to support the full sentence-transformers ML libraries without crashing.

### Step-by-Step Setup:
1. **Create an Account / Log In**: Go to [Hugging Face](https://huggingface.co/) and log in.
2. **Create a New Space**:
   - Go to **Spaces** -> **Create new Space**.
   - Enter a name (e.g., `ai-recruiter-screening`).
   - Select **Docker** as the SDK.
   - Choose the **Blank** template.
   - Keep it **Public** (or **Private** if preferred).
   - Click **Create Space**.
3. **Commit the Code**:
   - Hugging Face Spaces act as a Git repository. You can clone the space locally, copy your project files into it, and push, OR upload the files directly via the Hugging Face browser UI.
   - **Crucial step**: Hugging Face Spaces uses the file named `Dockerfile` in the root of the repository to build the container.
   - **Action**: Rename `Dockerfile.web` to `Dockerfile` when pushing to your Hugging Face Space repository, so that HF builds the web server instead of the offline script.
4. **Set Environment Variables**:
   - Go to your Space **Settings** tab.
   - Scroll down to **Variables and secrets**.
   - Add your secret keys as **Secrets** (add `GEMINI_API_KEY` and `SECRET_KEY`).
5. **Launch**:
   - Once the files are pushed, Hugging Face will automatically build and start the container. The web app will be live and accessible directly via the Space URL!

---

## ☁️ Option B: Render Deployment (Free Web Service - Memory-Constrained)
Render offers free hosting for web services but enforces a **512MB RAM limit**. To deploy on Render without running out of memory, we must use a lightweight requirements list that skips heavy local machine learning libraries (`torch`, `sentence-transformers`, `transformers`) and falls back to dynamic NumPy calculations or Pinecone cloud vectors.

### Step-by-Step Setup:
1. **Prepare Code on GitHub**: Push your AI Recruiter repository to GitHub.
2. **Create a Render Web Service**:
   - Go to the [Render Dashboard](https://dashboard.render.com/) and click **New** -> **Web Service**.
   - Connect your GitHub repository.
3. **Configure Service Settings**:
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements-prod.txt` (This installs the lightweight dependency list).
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Set Environment Variables**:
   - Click **Advanced** -> **Add Environment Variable**.
   - Add:
     - `GEMINI_API_KEY` = `your_gemini_api_key`
     - `SECRET_KEY` = `your_jwt_secret_key`
     - `DATABASE_URL` = `sqlite:///./recruiter.db` (or a PostgreSQL link if using one).
5. **Deploy**:
   - Click **Create Web Service**. Render will install the lightweight dependencies and start the app. The app will be available on your custom Render subdomain (`https://xxx.onrender.com`).

---

## 💾 Database Persistence (PostgreSQL Configuration)
By default, SQLite creates a local file `recruiter.db`. Since cloud hosts (Render/Hugging Face) have ephemeral storage, your database will reset every time the container restarts.

To ensure your recruiters and jobs persist:
1. Provision a free PostgreSQL database on [Supabase](https://supabase.com/) or [Neon DB](https://neon.tech/).
2. Copy the connection string.
3. Set the `DATABASE_URL` environment variable on your hosting provider to:
   ```env
   DATABASE_URL=postgresql://username:password@hostname:5432/databasename?sslmode=require
   ```
   *The application will automatically detect the database type on startup and initialize all required SQL tables.*

---

## 🚪 Post-Deployment Access & Default Credentials
Once the app is running:
- Access the web UI at the root domain: `http://<your-deployed-app-url>/`
- Log in with the pre-seeded admin or recruiter credentials:
  - **Recruiter Account**: `recruiter@recruiter.com` / Password: `recruiter123`
  - **Admin Account**: `admin@admin.com` / Password: `admin123`
- Inside the recruiter portal, you can customize recruiter credentials and start posting jobs and running evaluations!
