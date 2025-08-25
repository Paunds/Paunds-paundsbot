# PaundsBot (ProBot tarzı)

ProBot'a benzeyen çekirdek özellikler: hoş geldin + oto-rol, level/XP, moderasyon, log.

## Kurulum
```bash
# Python 3.10+
pip install -r requirements.txt

# .env dosyası oluştur (veya .env.example'ı kopyala)
cp .env.example .env
# ardından .env içini kendi ID ve tokenlarınla doldur
```

## Çalıştırma
```bash
python bot.py
```

## Gerekli Ayarlar
- Discord Developer Portal > Bot > **MESSAGE CONTENT** ve **SERVER MEMBERS** intents açık olmalı.
- Sunucu/kanal/rol kimlikleri için Discord > Ayarlar > Geliştirici Modu → sağ tık → **Kimliği Kopyala**.

## Komutlar
- `!help_paunds` - Yardım menüsü
- `!rank` - Seviye bilgisini göster
- `!clear <sayı>` - Kanalda mesaj siler
- `!kick @üye [sebep]` - Üyeyi atar
- `!ban @üye [sebep]` - Üyeyi yasaklar
- `!timeout @üye <dakika> [sebep]` - Zaman aşımı verir
