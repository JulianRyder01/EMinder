
ENV_NAME="EMinder_service"
PYTHON_VERSION="3.12"
BACKEND_PORT=8421
FRONTEND_PORT=10101

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_SCRIPT="$ROOT_DIR/backend/run.py"
FRONTEND_SCRIPT="$ROOT_DIR/frontend/run.py"
REQ_FILE="$ROOT_DIR/requirements.txt"

echo ""
echo "==================================================="
echo "       EMinder Launcher (Linux/macOS)"
echo "==================================================="
echo ""

CONDA_BASE=$(conda info --base 2>/dev/null)

if [ -z "$CONDA_BASE" ]; then
    echo "[ERROR] 'conda' command not found."
    echo "Please ensure Anaconda or Miniconda is installed and in your PATH."
    exit 1
fi

echo "[INFO] Initializing Conda..."
source "$CONDA_BASE/etc/profile.d/conda.sh"

if conda info --envs | grep -q "$ENV_NAME"; then
    echo "[INFO] Environment '$ENV_NAME' found."
else
    echo "[INFO] Environment not found. Creating '$ENV_NAME' (Python $PYTHON_VERSION)..."
    conda create -n "$ENV_NAME" python="$PYTHON_VERSION" -y
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create environment."
        exit 1
    fi
    echo "[INFO] Environment created successfully."
fi

echo "[INFO] Activating environment '$ENV_NAME'..."
conda activate "$ENV_NAME"
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate environment."
    exit 1
fi

if [ -f "$REQ_FILE" ]; then
    echo "[INFO] Checking dependencies (requirements.txt)..."
    pip install -r "$REQ_FILE"
    if [ $? -ne 0 ]; then
        echo "[ERROR] Dependency installation failed."
        exit 1
    fi
else
    echo "[WARNING] requirements.txt not found in root directory."
fi

echo ""
echo "[INFO] Starting EMinder Services..."

# Function to run command in a new terminal window
open_terminal() {
    local title="$1"
    local cmd="$2"

    # Detect Terminal Emulator
    if command -v gnome-terminal >/dev/null 2>&1; then
        gnome-terminal --title="$title" -- bash -c "$cmd; exec bash"
    elif command -v konsole >/dev/null 2>&1; then
        konsole --new-tab --title "$title" -e bash -c "$cmd; exec bash"
    elif command -v xterm >/dev/null 2>&1; then
        xterm -T "$title" -e "bash -c \"$cmd; exec bash\""
    elif command -v open >/dev/null 2>&1; then # macOS
        osascript -e "tell application \"Terminal\" to do script \"$cmd\""
    else
        return 1 # No supported terminal found
    fi
    return 0
}

ACTIVATE_CMD="source \"$CONDA_BASE/etc/profile.d/conda.sh\" && conda activate \"$ENV_NAME\""

RUN_BACKEND="$ACTIVATE_CMD && python \"$BACKEND_SCRIPT\" --port $BACKEND_PORT"
RUN_FRONTEND="$ACTIVATE_CMD && python \"$FRONTEND_SCRIPT\" --port $FRONTEND_PORT --bnport $BACKEND_PORT"

if [ -n "$DISPLAY" ] || [ "$(uname)" == "Darwin" ]; then
    echo "[INFO] GUI detected. Launching in separate windows..."
    
    open_terminal "EMinder Backend" "$RUN_BACKEND"
    if [ $? -eq 0 ]; then
        echo "[1/2] Backend launched."
        sleep 3
        open_terminal "EMinder Frontend" "$RUN_FRONTEND"
        echo "[2/2] Frontend launched."
    else

        echo "[WARNING] Could not launch terminal emulator. Falling back to background processes."
        eval "$RUN_BACKEND" &
        BACKEND_PID=$!
        sleep 3
        eval "$RUN_FRONTEND" &
        FRONTEND_PID=$!
        echo "[INFO] Services running in background (PIDs: $BACKEND_PID, $FRONTEND_PID)."
    fi
else

    echo "[INFO] No GUI detected. Launching in background..."
    
    nohup bash -c "$RUN_BACKEND" > backend.log 2>&1 &
    BACKEND_PID=$!
    echo "[1/2] Backend started (PID: $BACKEND_PID). Logs: backend.log"
    
    sleep 3
    
    nohup bash -c "$RUN_FRONTEND" > frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "[2/2] Frontend started (PID: $FRONTEND_PID). Logs: frontend.log"
fi

echo ""
echo "==================================================="
echo "       Launch Sequence Completed"
echo "==================================================="
echo " [Backend API] http://127.0.0.1:$BACKEND_PORT/docs"
echo " [Frontend UI] http://127.0.0.1:$FRONTEND_PORT"
echo ""
