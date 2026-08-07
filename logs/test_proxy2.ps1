$token = & "e:\ai_project\factor-quantization-trader\venv\Scripts\python.exe" -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.contrib.auth.models import User; from rest_framework_simplejwt.tokens import RefreshToken; u=User.objects.get(username='admin'); print(str(RefreshToken.for_user(u).access_token))"
Write-Host "--- limit=500 ---"
$t1 = (Measure-Command { curl.exe -s -o NUL --max-time 10 -H "Authorization: Bearer $token" "http://127.0.0.1:8000/api/market/klines/scroll/?inst_id=BTC-USDT&bar=1H&limit=500&auto_fetch=false" }).TotalSeconds
Write-Host "limit=500 auto_fetch=false: $t1 s"
Write-Host "--- limit=1000 ---"
$t2 = (Measure-Command { curl.exe -s -o NUL --max-time 10 -H "Authorization: Bearer $token" "http://127.0.0.1:8000/api/market/klines/scroll/?inst_id=BTC-USDT&bar=1H&limit=1000&auto_fetch=false" }).TotalSeconds
Write-Host "limit=1000 auto_fetch=false: $t2 s"
Write-Host "--- limit=1000 auto_fetch=true ---"
$t3 = (Measure-Command { curl.exe -s -o NUL --max-time 10 -H "Authorization: Bearer $token" "http://127.0.0.1:8000/api/market/klines/scroll/?inst_id=BTC-USDT&bar=1H&limit=1000&auto_fetch=true" }).TotalSeconds
Write-Host "limit=1000 auto_fetch=true: $t3 s"
