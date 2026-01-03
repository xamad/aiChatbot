# Xiaozhi ESP32 - Assistente Vocale Italiano

Chatbot vocale basato su ESP32 con supporto completo per la lingua italiana e oltre 50 funzioni vocali.

## Caratteristiche Principali

### Sistema Multi-Profilo
Il chatbot supporta **11 profili skill** ottimizzati per diversi casi d'uso:

| Profilo | Icona | Descrizione |
|---------|-------|-------------|
| `generale` | 🏠 | Assistente bilanciato per uso quotidiano |
| `anziani` | 👴 | Interfaccia semplificata, compagnia e supporto |
| `bambini` | 🧒 | Contenuti sicuri, giochi educativi |
| `intrattenimento` | 🎮 | Giochi, quiz, barzellette |
| `produttivita` | 📋 | Organizzazione, promemoria, note |
| `cultura_italiana` | 🇮🇹 | Notizie, cucina, tradizioni |
| `benessere` | 🧘 | Meditazione, supporto emotivo |
| `smart_home` | 🏡 | Domotica e IoT |
| `interprete` | 🌍 | Traduzione real-time multilingue |
| `cucina` | 👨‍🍳 | Ricette passo-passo |
| `notte` | 🌙 | Funzioni rilassanti per dormire |

**Comandi profili:**
- "Cambia profilo in [nome]"
- "Elenco profili"
- "Che profilo sono?"

---

## Funzioni Disponibili

### 🎯 Comandi Base (sempre attivi)
| Funzione | Trigger Vocali |
|----------|---------------|
| **Aiuto** | "aiuto", "help", "come funziona" |
| **Meteo** | "che tempo fa a Roma", "previsioni" |
| **Timer** | "timer 5 minuti", "svegliami tra..." |
| **Calcoli** | "quanto fa 15 per 8", "percentuale di..." |
| **Ricerca Web** | "cerca su internet...", "google..." |
| **AI Chat** | "chiedi a GPT...", "spiegami..." |

### 🎵 Audio e Media
| Funzione | Trigger Vocali |
|----------|---------------|
| **Radio Italia** | "metti radio deejay", "sintonizza radio zeta" |
| **Podcast** | "metti podcast", "ascolta podcast" |
| **Suoni Relax** | "suono della pioggia", "onde del mare" |
| **Beatbox** | "fai un beatbox", "base trap" |

### 🎮 Giochi e Intrattenimento
| Funzione | Trigger Vocali |
|----------|---------------|
| **Quiz Trivia** | "facciamo un quiz", "trivia" |
| **Impiccato** | "giochiamo a impiccato" |
| **20 Domande** | "venti domande", "indovina cosa penso" |
| **Battaglia Navale** | "battaglia navale" |
| **Barzellette** | "raccontami una barzelletta" |
| **Dado** | "lancia un dado", "testa o croce" |

### 👨‍🍳 Cucina
| Funzione | Trigger Vocali |
|----------|---------------|
| **Ricette** | "ricetta della carbonara" |
| **Con Ingredienti** | "cosa cucino con uova e pasta" |
| **Guida Cucina** | "cuciniamo la carbonara", "prossimo step" |
| **Lista Spesa** | "aggiungi latte alla spesa" |

### 🌍 Traduzione Real-Time
Il traduttore supporta modalità interprete continua con **TTS multilingue automatico**:

```
"traduttore in inglese"    → Avvia modalità interprete
"traduci ciao in spagnolo" → Traduzione singola
"stop" o "normale"         → Esci dalla modalità
```

**Lingue supportate:** Inglese, Francese, Spagnolo, Tedesco, Portoghese, Russo, Cinese, Giapponese, Coreano, Arabo, Greco, Olandese, Polacco, Turco, Hindi

### 📝 Produttività
| Funzione | Trigger Vocali |
|----------|---------------|
| **Promemoria** | "ricordami di...", "promemoria tra..." |
| **Note Vocali** | "prendi nota...", "annotazione" |
| **Memoria** | "ricordami che le chiavi sono...", "dove ho messo..." |
| **Rubrica** | "numero di Mario", "telefono di..." |
| **Agenda** | "cosa ho domani", "aggiungi appuntamento" |

### 📰 Informazioni Italia
| Funzione | Trigger Vocali |
|----------|---------------|
| **Notizie** | "notizie", "ultime news" |
| **Curiosità** | "dimmi una curiosità" |
| **Accadde Oggi** | "accadde oggi" |
| **Santo del Giorno** | "che santo è oggi" |
| **Oroscopo** | "oroscopo ariete" |
| **Proverbi** | "dimmi un proverbio" |
| **Lotto** | "estrazioni lotto" |

### 🧘 Benessere
| Funzione | Trigger Vocali |
|----------|---------------|
| **Meditazione** | "meditazione", "mindfulness" |
| **Supporto Emotivo** | "ho paura", "sono ansioso" |
| **Compagnia** | "mi sento solo", "fammi compagnia" |
| **Compagno Notturno** | "non riesco a dormire" |

### 👶 Bambini e Famiglia
| Funzione | Trigger Vocali |
|----------|---------------|
| **Storie** | "raccontami una storia", "favola" |
| **Versi Animali** | "fai il verso del gallo", "come fa la mucca" |
| **Barzellette Kids** | "barzelletta per bambini" |

### 🏠 Domotica (Smart Home)
| Funzione | Trigger Vocali |
|----------|---------------|
| **Controllo Luci** | "accendi luce salotto", "spegni cucina" |
| **Home Assistant** | "stato della casa", "temperatura" |
| **Mesh IoT** | Supporto rete mesh sensori/attuatori |

### 🎭 Personalità Multiple
```
"parla come un pirata"  → Modalità pirata
"fai il robot"          → Modalità robot
"fai il nonno burbero"  → Modalità nonno
"torna normale"         → Reset personalità
```

---

## Easter Eggs 🥚

### Giannino (EPICO!)
Dì "Giannino" o "chi è Giannini" per attivare l'easter egg dedicato.
Le frasi sono configurabili dalla WebUI.

### Osterie Goliardiche
```
"osteria numero 5"
"paraponziponzipò"
"canta osteria"
```

### Easter Egg Folli
```
"insultami"           → Insulti creativi
"confessami"          → Confessionale folle
"litiga con te stesso"
```

---

## Configurazione

### WebUI
Accedi alla WebUI su `http://[IP]:8002` per configurare:
- Provider TTS/ASR/LLM
- Frasi Easter Egg Giannino
- Stazioni Radio
- Home Assistant

### File di Configurazione
```
data/config/skill_profiles.py  # Profili skill
data/giannino_phrases.json     # Frasi Giannino
config.yaml                    # Config principale
```

---

## Architettura Tecnica

### Stack Tecnologico
- **ASR:** Groq Whisper (italiano)
- **TTS:** Edge TTS (multilingue automatico)
- **LLM:** Groq Llama 3.3 70B
- **Intent:** Pattern matching + LLM fallback

### TTS Multilingue Automatico
Il sistema rileva automaticamente la lingua del testo e seleziona la voce appropriata:
- Italiano → it-IT-ElsaNeural
- Cinese → zh-CN-XiaoxiaoNeural
- Giapponese → ja-JP-NanamiNeural
- Russo → ru-RU-SvetlanaNeural
- E altre 12 lingue...

### Sistema Watchdog
Monitoraggio automatico della salute del container con auto-recovery.

---

## Comandi Vocali Rapidi

| Cosa vuoi fare | Dì |
|----------------|-----|
| Aiuto generale | "aiuto" |
| Cambiare profilo | "cambia profilo in bambini" |
| Ascoltare radio | "metti radio deejay" |
| Tradurre | "traduttore in inglese" |
| Meteo | "che tempo fa a Milano" |
| Timer | "timer 10 minuti" |
| Barzelletta | "raccontami una barzelletta" |
| Quiz | "facciamo un quiz" |
| Ricetta | "ricetta della carbonara" |
| Notizie | "notizie" |
| Dormire | "suono della pioggia" |

---

## Licenza

Basato su [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) con estensioni italiane.

---

*Documentazione generata con Claude Code*
