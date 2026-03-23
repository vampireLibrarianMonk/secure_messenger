# Secure Messenger

Secure Messenger is a privacy-first messaging app with encrypted chat, encrypted file sharing, and WebRTC video calling.

- **Backend:** Django + DRF + Channels (ASGI)
- **Frontend:** Vue 3 + Vite + TypeScript + Pinia
- **Security model:** client-side encryption/decryption via WebCrypto; server stores ciphertext and encrypted file blobs.

## Current Features

- JWT auth (register/login/refresh/logout/me)
- Conversation creation and membership management
- Real-time chat via WebSockets
- Client-side encrypted text messages
- Client-side encrypted file upload + receiver-side decrypt/download
- Session lock controls (manual lock, inactivity timeout, local key wipe)
- WebRTC video calls with websocket signaling
- Video diagnostics (signaling test, local loopback, camera/mic test)
- Simplified video UI (start/join/end controls + collapsible debug tools)
- Distinct outgoing/incoming call ring sounds

## Project Structure

- `backend/` – Django API + Channels websocket service
- `frontend/` – Vue app

## Run Locally

> Important: run backend with an **ASGI server** (Daphne) so websocket/video signaling routes work.

### 1) Backend setup

```bash
cd backend
pip install -r requirements.txt
pip install daphne
python manage.py migrate
```

### 2) Start backend (ASGI + websockets)

```bash
cd backend
python -m daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

### 3) Frontend setup

```bash
cd frontend
npm install
```

### 4) Start frontend

From the **project root**:

```bash
VITE_API_BASE=http://127.0.0.1:8000/api VITE_WS_BASE=ws://127.0.0.1:8000 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5175
```

Or if you are already inside `frontend/`:

```bash
VITE_API_BASE=http://127.0.0.1:8000/api VITE_WS_BASE=ws://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5175
```

Open: `http://127.0.0.1:5175`

## Quick Validation Flow

1. Register/login two users in separate browser profiles.
2. Create/select a shared conversation.
3. Send encrypted messages both ways.
4. Upload a file from one side; verify receiver sees **Download ...** and can download.
5. Test video:
   - Caller presses **Start Call**
   - Receiver should see **Join Call** and incoming ring
   - Receiver presses **Join Call**
6. Use Video **Debug tools** for troubleshooting if needed.

## Optional Environment Notes

- `USE_POSTGRES=1` enables PostgreSQL settings (backend)
- `USE_REDIS=1` enables Redis channel layer (backend)

## Security Note

This project is a practical secure-messaging prototype. Do not treat it as production-ready cryptographic software without independent security review and hardening.
