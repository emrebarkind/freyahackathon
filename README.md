# Build the Builder: FREYA × YC Hackathon

**Görev:** Bankanın tahsilat brief'ini okuyup Freya üzerinde telefon ajanı **üreten** bir program (builder).
**Puan:** Üretilen ajanın simüle müşteri vakalarında doğru çözdüğü vakaların oranı.
**Süre:** Cumartesi 10 Ekim 13:00 → Pazar 11 Ekim 23:00 (İstanbul).

## Mimari: kendini test eden builder

```
brief ──► [1] Policy çıkarımı ──► [2] Senaryo üretimi (gizli hakemi taklit eden test seti)
              (atomik kurallar,        │
               outcome kodları,        ▼
               sayısal limitler) ► [3] Ajan derleme (system prompt + açılış + kapanış)
                                       │
                         ┌─────────────┴─────────────┐
                         ▼                           │
                   [4] Simülasyon + hakem ──fail──► [5] Optimizasyon (kök neden, overfit yok)
                         │ (train %70)                    │
                         ▼                                └──► tekrar [4]
                   holdout %30 ile doğrulama ──► Freya'ya deploy
```

- **Builder modeli:** `claude-opus-5-5` (adaptive thinking, extraction/derleme için `xhigh` effort)
- **Simüle müşteri + hakem:** `claude-sonnet-5-5`
- **Yerel ajan vekili:** `claude-haiku-5-5`. Freya'nın canlı ajanı küçük ve hızlı bir LLM ile çalışıyor; prompt zayıf modelde çalışıyorsa orada da çalışır.
- **Gerçek test:** `--runner freya` ile ajan Freya'ya deploy edilir ve `/chat/message` üzerinden gerçek ajanla konuşulur.

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env   # ANTHROPIC_API_KEY, FREYA_API_KEY, FREYA_WORKSPACE_ID doldur
python -m builder freya-check                                   # anahtar + default config kontrol
python -m builder build briefs/sample_collections_brief.md      # yerel döngü (Freya'sız)
python -m builder build <brief> --runner freya --deploy         # gerçek Freya ajanıyla
```

Çıktılar `runs/<zaman>/` altına yazılır: `policy.json`, `scenarios.json`, `agent_v*.json`, `results_*.json`, `system_prompt.md`.

## Freya API'den öğrendiklerimiz (`docs/freya/`)

- Base URL `https://app.freyavoice.ai/api/v2`, `Authorization: Bearer <key>`. Yanıt zarfı `{success, data:{message, result}}`.
- `POST /agents` → `config.llmConfig.{systemPrompt, firstMessage, firstMessageMode, tools[], farewellMessage, temperature}` + tts/stt/compliance (zorunlu; `GET /agents/defaults` ile doldur).
- Prompt değişkenleri `{{customer_name}}` sözdizimiyle yazılıyor, değerleri `customerVariables` ile geçiliyor.
- **Hızlı test döngüsü:** `POST /chat/message {agentId, message, callId?, customerVariables}` → `{response, callId, endedByAgent}`.
- **Freya'nın kendi değerlendirme araçları:** `POST /personas` (prompt + successCriteria + evaluationPrompt), `POST /simulations` (mode chat|voice, runsPerPersona), `POST /unit-tests` (tool_call / extraction / routing assertion'ları). Muhtemelen hakem de bunları kullanıyor, starter kit'te kontrol edeceğiz.
- Tools: `{type:"function", function:{name, handler, description, parameters, transition_to}, extraction_schema[], response_mapping[]}`.
- `postConversationAnalysis.insights` ile yapılandırılmış sonuç alanları (outcome kodu, söz verilen tarih/tutar) eklenebilir. Hakem outcome'u buradan okuyorsa kritik.

## 13:00'te yapılacaklar (sırayla)

1. Challenge sayfasını ve starter kit'i oku. Şunları not al: **puanlama nasıl yapılıyor** (outcome alanı mı, transcript mi, tool çağrısı mı?), değişken isimleri, beklenen outcome kodları, zorunlu tool'lar, kullanılacak LLM.
2. Freya hesabını aç, API key ve workspace id'yi `.env`'e yaz, `python -m builder freya-check` çalıştır.
3. Starter kit'teki platform detaylarını `platform_notes.md`'ye yaz (tool handler'ları, outcome mekanizması) ve `--platform-notes platform_notes.md` ile ver.
4. Gerçek brief ile ilk `build` çalışmasını yap. İlk skoru gör.
5. Starter kit'te örnek vakalar ya da değerlendirme formatı varsa senaryo üretecini birebir ona benzet. **Kazancın %80'i hakemi doğru taklit etmekte.**
6. Freya `simulations` ile resmi skora en yakın ölçümü al, sonra iterasyon yap.

## Kazanma stratejisi

- **Ölçmeden değişiklik yok:** her prompt değişikliğinde train/holdout skoru loglanıyor.
- **Overfit yok:** optimizer kök nedeni düzeltiyor; holdout düşüyorsa değişiklik geri alınıyor.
- **Genellenebilirlik:** builder hiçbir şeyi bu brief için hard-code etmiyor. Jüri farklı bir brief verse de çalışır. Bu, "builder that builds builders" vizyonunun kanıtı.
- **Güvenlik/uyum önce:** doğrulamadan önce hiçbir bilgi verilmez, limit dışı teklif yapılmaz, baskı dili kullanılmaz. Bunlar otomatik fail sebepleri.
- **Demo:** sonunda kısa bir video ve bir rapor (brief → policy → senaryolar → skor eğrisi) hazırlanacak. YC başvurusunda da kullanılabilir.

## Açık riskler

- Freya'nın ajan LLM'i, tool handler türleri ve outcome okuma mekanizması starter kit'e kadar belirsiz.
- Rate limit / maliyet: senaryo × iterasyon × tur. Gerekirse `--scenarios 12 --iterations 2` ile başla.
