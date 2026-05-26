# Pavement Simulator - Deploy to Hugging Face Spaces
# Run this script from the project directory

$HF_USER = "sourabh00809"
$SPACE_NAME = "pavement_simulator"
$HF_TOKEN = Read-Host -Prompt "Enter your Hugging Face token (get it from https://huggingface.co/settings/tokens)"

# Push to HF Space
git remote remove hf 2>$null
git remote add hf "https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${SPACE_NAME}"
git push hf master --force

Write-Host ""
Write-Host "Deploy triggered! Go to:" -ForegroundColor Green
Write-Host "https://huggingface.co/spaces/${HF_USER}/${SPACE_NAME}" -ForegroundColor Cyan
