VLLM_USE_V1=1
CKPT_PATH=/fsx/sfr/data/yutong/UI-TARS-2B-SFT
SERVED_MODEL_NAME=UI-TARS-2B-SFT

source /fsx/home/yutong/miniconda3/bin/activate
conda activate crmbench
which python

pkill -f "vllm.entrypoints.openai.api_server"

VLLM_LOG_FILE="vllm_log_file.log"

for PORT in 2025 2026 2027 2028 2029 2030 2031 2032; do
    GPU_ID=$((PORT - 2025))
    echo "Serving model $MODEL_NAME from $CKPT_PATH on the port $PORT with GPU $GPU_ID"
    CUDA_VISIBLE_DEVICES=$GPU_ID python3 -m vllm.entrypoints.openai.api_server \
        --api-key token-abc123 \
        --model $CKPT_PATH \
        --served-model-name $SERVED_MODEL_NAME \
        --host localhost \
        --port $PORT \
        --dtype bfloat16 \
        --tensor-parallel-size 1 \
        --limit-mm-per-prompt image=5,video=0 \
        --gpu-memory-utilization 0.9 \
        --max-model-len 32768 > $VLLM_LOG_FILE 2>&1 &    
done

for PORT in 2025 2026 2027 2028 2029 2030 2031 2032; do
    until curl -H "Authorization: Bearer token-abc123" http://localhost:$PORT/v1/models > /dev/null; do
        # echo "Waiting for vLLM server to start on port $PORT..."
        sleep 30
    done
    echo "vLLM server is ready on port $PORT."
done