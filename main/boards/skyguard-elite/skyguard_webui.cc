#include "skyguard_webui.h"
#include "settings.h"
#include "application.h"
#include <esp_log.h>
#include <esp_netif.h>
#include <cJSON.h>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <esp_heap_caps.h>

#define TAG "SkyGuardWebUI"

// =========================================================================
// Embedded HTML — full dashboard with display mirror + config
// =========================================================================

static const char WEBUI_HTML[] = R"rawhtml(<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SkyGuard AI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
.hdr{background:#161b22;padding:12px;text-align:center;border-bottom:2px solid #55aaff;position:sticky;top:0;z-index:10}
.hdr h1{color:#55aaff;font-size:1.3em}
.hdr p{color:#556677;font-size:.75em}
.tabs{display:flex;gap:0;background:#161b22;border-bottom:1px solid #21262d;position:sticky;top:52px;z-index:9}
.tab{flex:1;padding:10px;text-align:center;color:#8b949e;cursor:pointer;font-size:.85em;border-bottom:2px solid transparent}
.tab.active{color:#55aaff;border-bottom-color:#55aaff;background:#0d1117}
.panel{display:none;padding:12px;max-width:600px;margin:0 auto}
.panel.active{display:block}
.card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px;margin-bottom:12px;position:relative}
.card h3{font-size:.85em;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:6px}
.card h3 .dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.row{display:flex;justify-content:space-between;padding:3px 0;font-size:.82em}
.row .k{color:#8b949e}.row .v{color:#e0e0e0;font-weight:500}
.v.good{color:#00dd66}.v.warn{color:#ffbb00}.v.bad{color:#ff3333}.v.info{color:#55aaff}.v.dim{color:#667788}
.wx-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;text-align:center;font-size:.75em}
.wx-daily{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;text-align:center;font-size:.75em;margin-top:8px;padding-top:8px;border-top:1px solid #21262d}
.wx-col{background:#0d1117;border-radius:4px;padding:6px 2px}
.wx-col .t{color:#55aaff;font-weight:bold}.wx-col .c{font-size:1.4em;line-height:1.2}
.wx-col .w{color:#8b949e}.wx-col .tp{color:#e0e0e0;font-weight:bold}
.bar{height:4px;border-radius:2px;margin:4px auto;max-width:80%}
label{display:block;color:#8b949e;font-size:.8em;margin:8px 0 3px}
input[type=text],input[type=number]{width:100%;padding:7px 10px;background:#0d1117;border:1px solid #30363d;
border-radius:6px;color:#c9d1d9;font-size:.85em;margin-bottom:4px}
input:focus{border-color:#55aaff;outline:none}
.btn{padding:8px 16px;background:#238636;color:#fff;border:none;border-radius:6px;font-size:.85em;cursor:pointer;width:100%;margin-top:8px}
.btn:hover{background:#2ea043}
.msg{padding:8px;border-radius:6px;margin-bottom:8px;font-size:.8em;display:none}
.msg.show{display:block}
.msg.ok{background:#0d2818;border:1px solid #238636;color:#00dd66}
.msg.err{background:#2d0f0f;border:1px solid #da3633;color:#ff3333}
.eq-tab{flex:1;text-align:center;padding:6px;background:#0d1117;border:1px solid #21262d;border-radius:4px;cursor:pointer;color:#8b949e;font-size:.8em}
.eq-tab.active{color:#55aaff;border-color:#55aaff;background:#161b22}
.big{font-size:2em;font-weight:bold;text-align:center;padding:8px 0}
.sub{text-align:center;color:#8b949e;font-size:.8em}
.flight{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #0d1117;font-size:.8em}
.sat{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #0d1117;font-size:.8em}
footer{text-align:center;color:#30363d;font-size:.65em;padding:12px}
.cbtn{padding:8px 12px;background:#1a2332;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:.78em;cursor:pointer;text-align:left;flex:1 1 calc(50% - 4px);min-width:120px}
.cbtn:hover{background:#1f6feb;border-color:#1f6feb;color:#fff}
.cbtn:active{background:#238636;border-color:#238636}
.cbtn.sending{opacity:.5;pointer-events:none}
.acc-hdr{cursor:pointer;user-select:none}
.acc-hdr::after{content:' +';color:#55aaff;font-weight:bold}
.acc-hdr.open::after{content:' -'}
.rbtn{padding:4px 8px;background:#0d1117;border:1px solid #21262d;border-radius:4px;color:#8b949e;font-size:.72em;cursor:pointer}
.rbtn:hover{background:#1a2332;color:#c9d1d9}
</style>
</head>
<body>
<div class="hdr"><h1>SkyGuard AI</h1><p>Astronomy Copilot Dashboard</p></div>
<div class="tabs">
<div class="tab active" onclick="showTab(0)">Display</div>
<div class="tab" onclick="showTab(1)">Comandi AI</div>
<div class="tab" onclick="showTab(2)">Config</div>
<div class="tab" onclick="showTab(3)">Info</div>
</div>

<!-- TAB 0: DISPLAY MIRROR -->
<div class="panel active" id="p0">

<div class="card"><h3><span class="dot" style="background:#55ff55"></span>SKY QUALITY</h3>
<div class="big" id="d_sqm">--.- MPSAS</div>
<div class="sub" id="d_sqm_q">--</div>
<div class="row"><span class="k">Bortle</span><span class="v" id="d_bortle">--</span></div>
<div class="row"><span class="k">NELM</span><span class="v" id="d_nelm">--</span></div>
<div class="row"><span class="k">Lux</span><span class="v" id="d_lux">--</span></div>
<div class="row"><span class="k">IR</span><span class="v" id="d_ir">--</span></div>
</div>

<div class="card"><h3><span class="dot" style="background:#7700ee"></span><span id="d_spec_title">SPETTRO / LP</span></h3>
<div id="d_spectral" style="display:flex;gap:2px;height:60px;align-items:flex-end;margin:8px 0"></div>
<div class="row"><span class="k" id="d_lp_label">Sorgente LP</span><span class="v" id="d_lp_src">--</span></div>
<div class="row"><span class="k" id="d_sqi_label">SQI</span><span class="v" id="d_sqi">--</span></div>
<div class="row"><span class="k" id="d_sv_label">Verdetto</span><span class="v" id="d_spectral_verdict">--</span></div>
</div>

<div class="card"><h3><span class="dot" style="background:#cccc88"></span>LUNA & NOTTE</h3>
<div class="row"><span class="k">Fase</span><span class="v" id="d_moon_phase">--</span></div>
<div class="row"><span class="k">Illuminazione</span><span class="v" id="d_moon_illum">--</span></div>
<div class="row"><span class="k">Eta</span><span class="v" id="d_moon_age">--</span></div>
<div class="row"><span class="k">Altitudine</span><span class="v" id="d_moon_alt">--</span></div>
<div class="row"><span class="k">Tramonto</span><span class="v" id="d_sunset">--</span></div>
<div class="row"><span class="k">Buio astronomico</span><span class="v" id="d_astro_dark">--</span></div>
</div>

<div class="card"><h3><span class="dot" style="background:#55aaff"></span>PREVISIONI</h3>
<div style="color:#8b949e;font-size:.7em;margin-bottom:4px">Prossime 5 ore</div>
<div class="wx-grid" id="d_weather"></div>
<div style="color:#8b949e;font-size:.7em;margin-top:8px">Prossimi 5 giorni</div>
<div class="wx-daily" id="d_weather_daily"></div>
<div class="row" style="margin-top:6px"><span class="k">Verdetto</span><span class="v" id="d_wx_verdict">--</span></div>
</div>

<div class="card"><h3><span class="dot" style="background:#ff8800"></span>RADAR AEREI</h3>
<div id="d_flights"><div style="color:#556677;font-size:.8em">In attesa dati...</div></div>
</div>

<div class="card"><h3><span class="dot" style="background:#00ccff"></span>SATELLITI VISIBILI</h3>
<div id="d_sats"><div style="color:#556677;font-size:.8em">In attesa dati...</div></div>
</div>

<div class="card"><h3><span class="dot" style="background:#4488cc"></span>METEOSAT / NUBI</h3>
<div class="row"><span class="k">Nuvole ora</span><span class="v" id="d_clouds_now">--</span></div>
<div class="row"><span class="k">Condizioni</span><span class="v" id="d_sky_cond">--</span></div>
<div class="row"><span class="k">Visibilita</span><span class="v" id="d_visibility">--</span></div>
<div class="row"><span class="k">Finestre serene</span><span class="v" id="d_clear_win">--</span></div>
<div class="row"><span class="k">Verdetto</span><span class="v" id="d_sky_verdict">--</span></div>
</div>

<div class="card"><h3><span class="dot" style="background:#cc55ff"></span>TELESCOPIO</h3>
<div style="color:#8b949e;font-size:.7em;margin-bottom:4px">ASCOM Alpaca</div>
<div class="row"><span class="k">Stato</span><span class="v" id="d_scope_status">Non connesso</span></div>
<div class="row"><span class="k">RA</span><span class="v" id="d_scope_ra">--</span></div>
<div class="row"><span class="k">DEC</span><span class="v" id="d_scope_dec">--</span></div>
<div class="row"><span class="k">Tracking</span><span class="v" id="d_scope_track">--</span></div>
<div id="d_indi_section" style="display:none;margin-top:8px;padding-top:8px;border-top:1px solid #21262d">
<div style="color:#8b949e;font-size:.7em;margin-bottom:4px">INDI Server</div>
<div class="row"><span class="k">Stato</span><span class="v" id="d_indi_srv_status">--</span></div>
<div class="row"><span class="k">Profilo</span><span class="v" id="d_indi_profile">--</span></div>
<div class="row"><span class="k">Driver</span><span class="v" id="d_indi_drivers">--</span></div>
</div>
<div style="color:#556677;font-size:.75em;margin-top:6px">Configura ASCOM/INDI URL in Config</div>
</div>

<div class="card"><h3><span class="dot" style="background:#ff8844"></span>CONTROLLO TELESCOPIO</h3>
<div style="font-size:.8em;color:#8b949e">8 pulsanti touch sul display:</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:3px;margin-top:6px;font-size:.7em">
<div style="background:#1a3366;padding:4px;border-radius:3px;text-align:center;color:#aac">Track ON</div>
<div style="background:#1a3366;padding:4px;border-radius:3px;text-align:center;color:#aac">Track OFF</div>
<div style="background:#1a3366;padding:4px;border-radius:3px;text-align:center;color:#aac">Park</div>
<div style="background:#1a3366;padding:4px;border-radius:3px;text-align:center;color:#aac">Unpark</div>
<div style="background:#1a3366;padding:4px;border-radius:3px;text-align:center;color:#aac">Stop</div>
<div style="background:#1a3366;padding:4px;border-radius:3px;text-align:center;color:#aac">Home</div>
<div style="background:#1a4433;padding:4px;border-radius:3px;text-align:center;color:#aca">INDI Start</div>
<div style="background:#1a4433;padding:4px;border-radius:3px;text-align:center;color:#aca">INDI Stop</div>
</div>
</div>

<div class="card"><h3><span class="dot" style="background:#ff5544"></span>AMBIENTE</h3>
<div class="row"><span class="k">Temperatura</span><span class="v" id="d_temp">--</span></div>
<div class="row"><span class="k">Umidita</span><span class="v" id="d_hum">--</span></div>
<div class="row"><span class="k">Punto rugiada</span><span class="v" id="d_dew">--</span></div>
<div class="row"><span class="k">Spread</span><span class="v" id="d_spread">--</span></div>
<div class="row"><span class="k">Condensa</span><span class="v" id="d_cond">--</span></div>
</div>

<div class="card" id="dew_card" style="display:none"><h3><span class="dot" style="background:#ff6600"></span>DEW HEATER</h3>
<div class="row"><span class="k">Modo</span><span class="v" id="d_dew_mode">--</span></div>
<div class="row"><span class="k">Attivo</span><span class="v" id="d_dew_active">--</span></div>
<div class="row"><span class="k">Potenza</span><span class="v" id="d_dew_power">--</span></div>
<div class="row"><span class="k">GPIO</span><span class="v" id="d_dew_gpio">--</span></div>
<div class="row"><span class="k">Soglia spread</span><span class="v" id="d_dew_thr">--</span></div>
</div>

<div class="card"><h3><span class="dot" style="background:#00dd66"></span>GPS / POSIZIONE</h3>
<div class="row"><span class="k">Latitudine</span><span class="v" id="d_lat">--</span></div>
<div class="row"><span class="k">Longitudine</span><span class="v" id="d_lon">--</span></div>
<div class="row"><span class="k">Altitudine</span><span class="v" id="d_alt">--</span></div>
<div class="row"><span class="k">Satelliti GPS</span><span class="v" id="d_sats_gps">--</span></div>
<div class="row"><span class="k">Sorgente</span><span class="v" id="d_gps_src">--</span></div>
<div class="row"><span class="k">WiFi RSSI</span><span class="v" id="d_rssi">--</span></div>
</div>

<div class="card"><h3><span class="dot" style="background:#ffbb00"></span>EQUIPMENT</h3>
<div id="d_equip"><div style="color:#556677;font-size:.8em">Nessun setup configurato. Vai su Config per aggiungere.</div></div>
</div>

<div class="card"><h3><span class="dot" style="background:#55aaff"></span>FORECAST SYNC</h3>
<div class="row"><span class="k">Ultimo invio</span><span class="v" id="d_fc_last">--</span></div>
<div class="row"><span class="k">Slot inviati</span><span class="v" id="d_fc_slots">--</span></div>
<div class="row"><span class="k">Prossimo invio</span><span class="v" id="d_fc_next">--</span></div>
<div class="row"><span class="k">Stato</span><span class="v" id="d_fc_status">--</span></div>
</div>

<div class="card" id="stel_card" style="display:none"><h3><span class="dot" style="background:#dd88ff"></span>STELLARIUM</h3>
<div class="row"><span class="k">URL</span><span class="v" id="d_stel_url">--</span></div>
<div class="row"><span class="k">Stato</span><span class="v" id="d_stel_status">--</span></div>
</div>

</div>

<!-- TAB 1: COMANDI AI -->
<div class="panel" id="p1">
<div id="cmdStatus" style="display:flex;align-items:center;gap:6px;margin-bottom:8px;font-size:.8em">
<span id="cmdDot" style="width:8px;height:8px;border-radius:50%;background:#ffbb00"></span>
<span id="cmdState">Pronto</span>
</div>

<div id="cmdResponse" class="card" style="display:none">
<h3><span class="dot" style="background:#55aaff"></span>Risposta AI</h3>
<div id="cmdRespText" style="font-size:.82em;white-space:pre-wrap;max-height:200px;overflow-y:auto"></div>
</div>

<div id="cmdRecent" class="card" style="display:none">
<h3>Recenti</h3>
<div id="cmdRecentList" style="display:flex;flex-wrap:wrap;gap:4px"></div>
</div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Osservazione</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Analizza le condizioni del cielo stasera')">Condizioni cielo</button>
<button class="cbtn" onclick="sendCmd('Qual e il seeing stimato?')">Seeing stimato</button>
<button class="cbtn" onclick="sendCmd('Quando inizia il buio astronomico?')">Buio astronomico</button>
<button class="cbtn" onclick="sendCmd('Quanto dura la finestra osservativa stasera?')">Finestra osservativa</button>
<button class="cbtn" onclick="sendCmd('La Luna disturba stasera?')">Disturbo Luna</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Oggetti Deep Sky</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Suggerisci 5 oggetti deep sky visibili adesso')">Suggerisci 5 oggetti</button>
<button class="cbtn" onclick="sendCmd('Quali nebulose sono alte sopra i 40 gradi?')">Nebulose alte</button>
<button class="cbtn" onclick="sendCmd('Galassie facili per stasera')">Galassie facili</button>
<button class="cbtn" onclick="sendCmd('Oggetti Messier al meridiano')">Messier al meridiano</button>
<button class="cbtn" onclick="sendCmd('Oggetti per camera widefield')">Per widefield</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Pianificazione Imaging</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Pianifica sessione di imaging per stasera')">Pianifica sessione</button>
<button class="cbtn" onclick="sendCmd('Quanto tempo di esposizione serve per M42?')">Esposizione M42</button>
<button class="cbtn" onclick="sendCmd('Suggerisci filtri per questo livello di LP')">Filtri per LP</button>
<button class="cbtn" onclick="sendCmd('Calcola il campo inquadrato del mio setup')">Campo inquadrato</button>
<button class="cbtn" onclick="sendCmd('Crea un mosaico per la Nebulosa Velo')">Mosaico Velo</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Pianeti e Luna</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Quali pianeti sono visibili stasera?')">Pianeti visibili</button>
<button class="cbtn" onclick="sendCmd('Quando sorge Giove?')">Sorgere Giove</button>
<button class="cbtn" onclick="sendCmd('Quando sorge Saturno?')">Sorgere Saturno</button>
<button class="cbtn" onclick="sendCmd('Fase lunare dettagliata')">Fase lunare</button>
<button class="cbtn" onclick="sendCmd('Prossima congiunzione planetaria')">Congiunzione</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Meteo e Nubi</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Previsioni meteo per stasera')">Meteo stasera</button>
<button class="cbtn" onclick="sendCmd('Quando si aprono le nubi?')">Apertura nubi</button>
<button class="cbtn" onclick="sendCmd('Rischio rugiada sulle ottiche?')">Rischio rugiada</button>
<button class="cbtn" onclick="sendCmd('Vento e turbolenza previsti')">Vento e turbolenza</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Telescopio</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Stato del telescopio')">Stato telescopio</button>
<button class="cbtn" onclick="sendCmd('Punta il telescopio su M31')">Punta M31</button>
<button class="cbtn" onclick="sendCmd('Punta il telescopio su M42')">Punta M42</button>
<button class="cbtn" onclick="sendCmd('Centra il telescopio sullo zenith')">Vai allo zenith</button>
<button class="cbtn" onclick="sendCmd('Parcheggia il telescopio')">Parcheggia</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Sensori e Misure</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Misura SQM adesso')">Misura SQM</button>
<button class="cbtn" onclick="sendCmd('Analisi spettrale del cielo')">Analisi spettrale</button>
<button class="cbtn" onclick="sendCmd('Report completo sensori')">Report sensori</button>
<button class="cbtn" onclick="sendCmd('Storico misurazioni SQM di stasera')">Storico SQM</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Educazione</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Cosa significa Bortle 5?')">Scala Bortle</button>
<button class="cbtn" onclick="sendCmd('Come si legge il valore MPSAS?')">Guida MPSAS</button>
<button class="cbtn" onclick="sendCmd('Cos e il seeing astronomico?')">Cos e il seeing</button>
<button class="cbtn" onclick="sendCmd('Come ridurre l inquinamento luminoso nelle foto?')">Ridurre LP</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Aerei e Satelliti</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Aerei sopra di me adesso')">Aerei sopra</button>
<button class="cbtn" onclick="sendCmd('Prossimo passaggio ISS')">Passaggio ISS</button>
<button class="cbtn" onclick="sendCmd('Satelliti visibili stasera')">Satelliti visibili</button>
<button class="cbtn" onclick="sendCmd('C e rischio di scie nelle foto?')">Rischio scie</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Setup e Equipment</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Analizza il mio setup per stasera')">Analizza setup</button>
<button class="cbtn" onclick="sendCmd('Quale setup e migliore per nebulose?')">Setup nebulose</button>
<button class="cbtn" onclick="sendCmd('Limite di vento per la mia montatura')">Limite vento</button>
<button class="cbtn" onclick="sendCmd('Risoluzione e campionamento del mio setup')">Campionamento</button>
</div></div>

<div class="card"><h3 class="acc-hdr" onclick="toggleAcc(this)">Comandi Rapidi</h3>
<div class="acc-body" style="display:none;flex-wrap:wrap;gap:4px">
<button class="cbtn" onclick="sendCmd('Buonasera Sophia, come va stasera?')">Saluta Sophia</button>
<button class="cbtn" onclick="sendCmd('Riassumi la situazione')">Riassunto</button>
<button class="cbtn" onclick="sendCmd('Cosa mi consigli di fare adesso?')">Consiglio</button>
<button class="cbtn" onclick="sendCmd('Grazie Sophia, buonanotte')">Buonanotte</button>
</div></div>

</div>

<!-- TAB 2: CONFIGURATION -->
<div class="panel" id="p2">
<div id="cfgMsg" class="msg"></div>

<div class="card"><h3>API Keys</h3>
<label>OpenWeatherMap</label><input type="text" id="c_owm" placeholder="OWM API key">
<label>N2YO Satelliti</label><input type="text" id="c_n2yo" placeholder="N2YO API key">
<label>Google Geolocation</label><input type="text" id="c_google" placeholder="Google API key">
</div>

<div class="card"><h3>Posizione Fallback</h3>
<label>Latitudine</label><input type="number" id="c_lat" step="0.0001" placeholder="44.9019">
<label>Longitudine</label><input type="number" id="c_lon" step="0.0001" placeholder="8.1662">
</div>

<div class="card"><h3>Server SQM</h3>
<label>URL Server</label><input type="text" id="c_sqm_url" placeholder="https://sqm.xamad.net">
<label>API Key</label><input type="text" id="c_sqm_key" placeholder="SQM API key">
<div style="margin-top:8px"><label style="display:flex;align-items:center;gap:6px;cursor:pointer"><input type="checkbox" id="c_sqm_privacy"> Privacy — nascondi posizione in mappa pubblica</label></div>
<p style="color:#556677;font-size:.7em">Se attivo, i dati SQM vengono inviati senza coordinate GPS. La lettura non compare sulla mappa pubblica.</p>
</div>

<div class="card"><h3>Display</h3>
<label>Auto-scroll (secondi)</label><input type="number" id="c_scroll" value="5" min="2" max="30">
<label>Intervallo meteo (minuti)</label><input type="number" id="c_wx_int" value="30" min="5" max="120">
<label>Intervallo aerei (minuti)</label><input type="number" id="c_air_int" value="5" min="2" max="30">
</div>

<div class="card"><h3>Calibrazione Sensori</h3>
<label>Offset temperatura AHT20 (C)</label><input type="number" id="c_temp_off" step="0.1" value="-2.4" placeholder="-2.4">
<p style="color:#556677;font-size:.7em">Compensa riscaldamento SoC. Negativo = abbassa la lettura.</p>
<label>Offset umidita AHT20 (%)</label><input type="number" id="c_hum_off" step="0.1" value="0" placeholder="0">
<label>Soglia luce notte (lux)</label><input type="number" id="c_lux_thr" step="0.1" value="1.0" placeholder="1.0">
<p style="color:#556677;font-size:.7em">Sotto questa soglia il device considera notte (auto-misura SQM, night mode).</p>
<label>Soglia notte auto night-mode (lux)</label><input type="number" id="c_night_thr" step="0.1" value="10.0" placeholder="10.0">
</div>

<div class="card"><h3>Strumentazione Astronomica</h3>
<p style="color:#8b949e;font-size:.75em;margin-bottom:8px">Configura il tuo equipaggiamento completo. I dati vengono inviati al server per analisi AI accurata (suggerimenti setup, limiti vento, filtri per LP, ecc.)</p>
<div id="eq_cats" style="display:flex;flex-wrap:wrap;gap:3px;margin-bottom:10px">
<div class="eq-tab active" onclick="showCat('telescopes')">Telescopi</div>
<div class="eq-tab" onclick="showCat('cameras')">Camere</div>
<div class="eq-tab" onclick="showCat('mounts')">Montature</div>
<div class="eq-tab" onclick="showCat('filters')">Filtri</div>
<div class="eq-tab" onclick="showCat('optical_accessories')">Ottici</div>
<div class="eq-tab" onclick="showCat('thermal_accessories')">Termici</div>
<div class="eq-tab" onclick="showCat('power')">Alim.</div>
<div class="eq-tab" onclick="showCat('eyepieces')">Oculari</div>
<div class="eq-tab" onclick="showCat('setups')">Setup</div>
</div>
<div id="eq_content"></div>
<button class="btn" style="background:#1f6feb;margin-top:6px" onclick="addItem()">+ Aggiungi</button>
</div>

<div class="card"><h3>Controllo Remoto</h3>
<label>ASCOM Alpaca URL (Telescopio)</label><input type="text" id="c_alpaca" placeholder="http://192.168.1.x:11111">
<label>NINA Sequencer URL</label><input type="text" id="c_nina" placeholder="http://192.168.1.x:1888">
<label>PHD2 Autoguida URL</label><input type="text" id="c_phd2" placeholder="http://192.168.1.x:4400">
<label>Stellarium Remote URL</label><input type="text" id="c_stellarium" placeholder="http://192.168.1.x:8090">
<label>INDI Web Manager URL</label><input type="text" id="c_indi" placeholder="http://192.168.1.x:8624">
</div>

<div class="card"><h3>Dew Heater (Anticondensa)</h3>
<label>GPIO Pin</label><input type="number" id="c_dew_gpio" min="-1" max="48" placeholder="-1 (non configurato)">
<p style="color:#556677;font-size:.7em">Pin GPIO per relay/MOSFET fascia anticondensa. -1 = disabilitato.</p>
<label>Soglia spread (C)</label><input type="number" id="c_dew_thr" step="0.1" value="3.0" placeholder="3.0">
<p style="color:#556677;font-size:.7em">In modo AUTO si accende quando (temperatura - punto rugiada) &lt; soglia.</p>
</div>

<button class="btn" onclick="saveConfig()">Salva Configurazione</button>
</div>

<!-- TAB 3: INFO -->
<div class="panel" id="p3">
<div class="card"><h3>Dispositivo</h3>
<div class="row"><span class="k">Modello</span><span class="v">SkyGuard AI</span></div>
<div class="row"><span class="k">Firmware</span><span class="v">v2.1.0</span></div>
<div class="row"><span class="k">Board</span><span class="v">ESP32-S3 LCDWiki 2.8"</span></div>
<div class="row"><span class="k">PSRAM</span><span class="v">8MB</span></div>
<div class="row"><span class="k">IP</span><span class="v info" id="i_ip">--</span></div>
<div class="row"><span class="k">MAC</span><span class="v" id="i_mac">--</span></div>
<div class="row"><span class="k">Uptime</span><span class="v" id="i_uptime">--</span></div>
<div class="row"><span class="k">Heap libero</span><span class="v" id="i_heap">--</span></div>
</div>
<div class="card"><h3>Sensori</h3>
<div class="row"><span class="k">TSL2591 (SQM)</span><span class="v" id="i_tsl">--</span></div>
<div class="row"><span class="k">AS7341 (Spettro)</span><span class="v" id="i_as7">--</span></div>
<div class="row"><span class="k">AHT20 (Ambiente)</span><span class="v" id="i_aht">--</span></div>
<div class="row"><span class="k">GPS</span><span class="v" id="i_gps">--</span></div>
</div>
</div>

<footer>SkyGuard AI &copy; 2026</footer>

<script>
function showTab(n){
document.querySelectorAll('.tab').forEach((t,i)=>{t.classList.toggle('active',i===n)});
document.querySelectorAll('.panel').forEach((p,i)=>{p.classList.toggle('active',i===n)});
}

const wxIcons={clear:'\u2600',cloud:'\u2601',rain:'\u2602',snow:'\u2744',thunder:'\u26A1',partly:'\u26C5'};
function wxIcon(clouds,desc){
if(!desc)return wxIcons.cloud;
const d=desc.toLowerCase();
if(d.includes('temporale')||d.includes('thunder'))return wxIcons.thunder;
if(d.includes('neve')||d.includes('snow'))return wxIcons.snow;
if(d.includes('piog')||d.includes('rain')||d.includes('shower'))return wxIcons.rain;
if(clouds<15)return wxIcons.clear;
if(clouds<50)return wxIcons.partly;
return wxIcons.cloud;
}
function barColor(v){return v>60?'#ff3333':v>30?'#ffbb00':'#00dd66'}

function showMsg(txt,ok){
const m=document.getElementById('cfgMsg');
m.className='msg show '+(ok?'ok':'err');
m.textContent=txt;
setTimeout(()=>m.classList.remove('show'),3000);
}

async function loadStatus(){
try{
const r=await fetch('/api/status');const d=await r.json();
// SQM
if(d.sqm!==undefined){document.getElementById('d_sqm').textContent=d.sqm.toFixed(2)+' MPSAS';
document.getElementById('d_sqm').style.color=d.sqm>20?'#00dd66':d.sqm>18?'#ffbb00':'#ff3333'}
if(d.sqm_quality)document.getElementById('d_sqm_q').textContent=d.sqm_quality;
if(d.bortle!==undefined)document.getElementById('d_bortle').textContent='Classe '+d.bortle;
if(d.nelm!==undefined)document.getElementById('d_nelm').textContent=d.nelm.toFixed(1)+' mag';
if(d.lux!==undefined)document.getElementById('d_lux').textContent=d.lux.toFixed(4);
if(d.ir!==undefined)document.getElementById('d_ir').textContent=d.ir;
// Spectral
if(d.spectral){const c=['#7700ee','#0044ff','#00bbff','#00cc44','#99cc00','#ff8800','#ff2200','#bb0000'];
const n=['415','445','480','515','555','590','630','680'];
let h='';const mx=Math.max(...d.spectral,1);
d.spectral.forEach((v,i)=>{const pct=Math.max(v/mx*100,5);
h+=`<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end">
<div style="font-size:.6em;color:#888">${v}</div>
<div style="width:80%;height:${pct}%;background:${c[i]};border-radius:2px;min-height:3px"></div>
<div style="font-size:.55em;color:#556677;margin-top:2px">${n[i]}</div></div>`});
document.getElementById('d_spectral').innerHTML=h}
// Context-aware spectral labels (daytime=atmosphere, night=LP)
if(d.is_daytime){
document.getElementById('d_spec_title').textContent='ATMOSFERA';
document.getElementById('d_lp_label').textContent='Cielo';
document.getElementById('d_sqi_label').textContent='Trasparenza';
document.getElementById('d_sv_label').textContent='Foto Solare';
if(d.lp_source){const el=document.getElementById('d_lp_src');el.textContent=d.lp_source;
const sky=d.lp_source;el.className='v '+(sky.includes('Sereno')?'good':sky.includes('Poco')||sky.includes('Parz')?'warn':'bad')}
if(d.atm_clarity!==undefined){const el=document.getElementById('d_sqi');el.textContent=d.atm_clarity+'%';
el.className='v '+(d.atm_clarity>=60?'good':d.atm_clarity>=30?'warn':'bad')}
if(d.spectral_verdict){const el=document.getElementById('d_spectral_verdict');el.textContent=d.spectral_verdict;
el.className='v '+(d.spectral_verdict.includes('Eccellente')?'good':d.spectral_verdict.includes('Buono')?'warn':'bad')}
}else{
document.getElementById('d_spec_title').textContent='SPETTRO / LP';
document.getElementById('d_lp_label').textContent='Sorgente LP';
document.getElementById('d_sqi_label').textContent='SQI';
document.getElementById('d_sv_label').textContent='Verdetto';
if(d.lp_source){const el=document.getElementById('d_lp_src');el.textContent=d.lp_source;
el.className='v '+(d.lp_source.includes('Naturale')?'good':d.lp_source.includes('LED')||d.lp_source.includes('Misto')?'warn':'bad')}
if(d.sqi!==undefined){const el=document.getElementById('d_sqi');el.textContent=d.sqi+'%';
el.className='v '+(d.sqi>=70?'good':d.sqi>=40?'warn':'bad')}
if(d.spectral_verdict){const el=document.getElementById('d_spectral_verdict');el.textContent=d.spectral_verdict;
el.className='v '+(d.spectral_verdict.includes('Eccellente')||d.spectral_verdict.includes('Buono')?'good':
d.spectral_verdict.includes('Discreto')?'warn':'bad')}
}
// Moon
if(d.moon_phase)document.getElementById('d_moon_phase').textContent=d.moon_phase;
if(d.moon_illum!==undefined){const el=document.getElementById('d_moon_illum');el.textContent=d.moon_illum.toFixed(0)+'%';
el.className='v '+(d.moon_illum<30?'good':d.moon_illum<60?'warn':'bad')}
if(d.moon_age!==undefined)document.getElementById('d_moon_age').textContent=d.moon_age.toFixed(1)+' giorni';
if(d.moon_alt!==undefined){const el=document.getElementById('d_moon_alt');el.textContent=d.moon_alt.toFixed(1)+'\u00B0';
el.className='v '+(d.moon_alt<0?'good':'warn')}
if(d.sunset)document.getElementById('d_sunset').textContent=d.sunset;
if(d.astro_dark)document.getElementById('d_astro_dark').textContent=d.astro_dark;
// Weather hourly
if(d.weather&&d.weather.length){let h='';
d.weather.forEach(w=>{h+=`<div class="wx-col"><div class="t">${w.time||'--'}</div>
<div class="c">${wxIcon(w.clouds,w.desc)}</div>
<div class="bar" style="background:${barColor(w.clouds)};width:${Math.max(w.clouds,10)}%"></div>
<div style="color:${barColor(w.clouds)}">${w.clouds}%</div>
<div class="w">${w.wind.toFixed(0)}m/s</div>
<div class="tp">${w.temp.toFixed(0)}\u00B0</div></div>`});
document.getElementById('d_weather').innerHTML=h}
// Weather daily
if(d.weather_daily&&d.weather_daily.length){let h='';
d.weather_daily.forEach(dd=>{h+=`<div class="wx-col"><div class="t">${dd.day||'--'}</div>
<div class="c">${wxIcon(dd.clouds,dd.desc)}</div>
<div style="color:${barColor(dd.clouds)};font-size:.9em">${dd.clouds}%</div>
<div class="tp">${dd.tmin.toFixed(0)}\u00B0/${dd.tmax.toFixed(0)}\u00B0</div>
<div class="w">${dd.wind.toFixed(0)}m/s</div></div>`});
document.getElementById('d_weather_daily').innerHTML=h}
// Weather verdict
if(d.wx_verdict){const el=document.getElementById('d_wx_verdict');el.textContent=d.wx_verdict;
el.className='v '+(d.wx_verdict.includes('FAVOREVOLE')&&!d.wx_verdict.includes('NON')?'good':d.wx_verdict.includes('PARZIALE')?'warn':'bad')}
// Flights
if(d.flights!==undefined){if(d.flights.length===0){document.getElementById('d_flights').innerHTML='<div style="color:#556677;font-size:.8em">Nessun aereo rilevato</div>'}
else{let h='';d.flights.forEach(f=>{const c=f.dist>20?'good':f.dist>10?'warn':'bad';
h+=`<div class="flight"><span class="v ${c}">${f.cs} ${f.type||''}</span><span>${f.dir} ${f.dist.toFixed(1)}km FL${f.fl}</span></div>`});
h+=`<div style="color:#556677;font-size:.7em;margin-top:4px">${d.flights.length} aerei</div>`;
document.getElementById('d_flights').innerHTML=h}}
// Satellites
if(d.satellites!==undefined){if(d.satellites.length===0){document.getElementById('d_sats').innerHTML='<div style="color:#556677;font-size:.8em">Nessun passaggio previsto</div>'}
else{let h='';d.satellites.forEach(s=>{const c=s.mag<0?'good':s.mag<3?'warn':'';
h+=`<div class="sat"><span class="v ${c}">${s.name}</span><span>${s.time} Max${s.elev.toFixed(0)}\u00B0 ${s.dur}min</span></div>`});
document.getElementById('d_sats').innerHTML=h}}
// Meteosat / clouds
if(d.weather&&d.weather.length){const w0=d.weather[0];
document.getElementById('d_clouds_now').textContent=w0.clouds+'%';
document.getElementById('d_clouds_now').className='v '+(w0.clouds<30?'good':w0.clouds<60?'warn':'bad');
document.getElementById('d_sky_cond').textContent=w0.desc||'--';
if(d.visibility)document.getElementById('d_visibility').textContent=d.visibility;
let cw=0;d.weather.forEach(w=>{if(w.clouds<30)cw++});
document.getElementById('d_clear_win').textContent=cw+'/'+d.weather.length+'h';
document.getElementById('d_clear_win').className='v '+(cw>=4?'good':cw>=2?'warn':'bad');
const v=cw>=4?'CIELO FAVOREVOLE':cw>=2?'PARZIALE':'NON FAVOREVOLE';
document.getElementById('d_sky_verdict').textContent=v;
document.getElementById('d_sky_verdict').className='v '+(cw>=4?'good':cw>=2?'warn':'bad')}
// Telescope
if(d.scope_status){document.getElementById('d_scope_status').textContent=d.scope_status;
document.getElementById('d_scope_status').className='v '+(d.scope_status==='TRACKING'?'good':d.scope_status==='SLEWING'?'warn':'info')}
if(d.scope_ra)document.getElementById('d_scope_ra').textContent=d.scope_ra;
if(d.scope_dec)document.getElementById('d_scope_dec').textContent=d.scope_dec;
if(d.scope_tracking!==undefined)document.getElementById('d_scope_track').textContent=d.scope_tracking?'ON':'OFF';
// Dew heater
if(d.dew_mode!==undefined){document.getElementById('dew_card').style.display='block';
document.getElementById('d_dew_mode').textContent=d.dew_mode;
const da=d.dew_active;document.getElementById('d_dew_active').textContent=da?'SI':'NO';
document.getElementById('d_dew_active').className='v '+(da?'warn':'good');
document.getElementById('d_dew_power').textContent=d.dew_power+'%';
document.getElementById('d_dew_gpio').textContent='GPIO '+d.dew_gpio;
document.getElementById('d_dew_thr').textContent=d.dew_threshold.toFixed(1)+'\u00B0C'}
// Forecast sync
if(d.fc_last)document.getElementById('d_fc_last').textContent=d.fc_last;
if(d.fc_slots!==undefined)document.getElementById('d_fc_slots').textContent=d.fc_slots+' slot (5gg)';
if(d.fc_next)document.getElementById('d_fc_next').textContent=d.fc_next;
if(d.fc_status){const el=document.getElementById('d_fc_status');el.textContent=d.fc_status;
el.className='v '+(d.fc_status==='OK'?'good':d.fc_status==='Fetching'?'warn':'bad')}
// Stellarium
if(d.stellarium_url){document.getElementById('stel_card').style.display='block';
document.getElementById('d_stel_url').textContent=d.stellarium_url;
document.getElementById('d_stel_status').textContent=d.stel_ok?'Connesso':'Configurato';
document.getElementById('d_stel_status').className='v '+(d.stel_ok?'good':'info')}
// INDI (in telescope card)
if(d.indi_url||d.indi_running!==undefined){document.getElementById('d_indi_section').style.display='block';
if(d.indi_running!==undefined){document.getElementById('d_indi_srv_status').textContent=d.indi_running?'Attivo':'Fermo';
document.getElementById('d_indi_srv_status').className='v '+(d.indi_running?'good':'warn')}
if(d.indi_profile)document.getElementById('d_indi_profile').textContent=d.indi_profile;
if(d.indi_drivers!==undefined)document.getElementById('d_indi_drivers').textContent=d.indi_drivers+' attivi'}
// Environment
if(d.temp!==undefined)document.getElementById('d_temp').textContent=d.temp.toFixed(1)+'\u00B0C';
if(d.hum!==undefined)document.getElementById('d_hum').textContent=d.hum.toFixed(1)+'%';
if(d.dew!==undefined)document.getElementById('d_dew').textContent=d.dew.toFixed(1)+'\u00B0C';
if(d.spread!==undefined){const el=document.getElementById('d_spread');el.textContent=d.spread.toFixed(1)+'\u00B0C';
el.className='v '+(d.spread>5?'good':d.spread>2?'warn':'bad')}
if(d.condensation!==undefined){const el=document.getElementById('d_cond');
el.textContent=d.condensation?'RISCHIO':'OK';el.className='v '+(d.condensation?'bad':'good')}
// GPS
if(d.lat!==undefined)document.getElementById('d_lat').textContent=d.lat.toFixed(6);
if(d.lon!==undefined)document.getElementById('d_lon').textContent=d.lon.toFixed(6);
if(d.gps_alt!==undefined)document.getElementById('d_alt').textContent=d.gps_alt.toFixed(1)+'m';
if(d.gps_sats!==undefined)document.getElementById('d_sats_gps').textContent=d.gps_sats;
if(d.gps_source)document.getElementById('d_gps_src').textContent=d.gps_source;
if(d.rssi!==undefined)document.getElementById('d_rssi').textContent=d.rssi+' dBm';
// Info
if(d.ip)document.getElementById('i_ip').textContent=d.ip;
if(d.mac)document.getElementById('i_mac').textContent=d.mac;
if(d.uptime!==undefined){const h=Math.floor(d.uptime/3600),m=Math.floor((d.uptime%3600)/60);
document.getElementById('i_uptime').textContent=h+'h '+m+'m'}
if(d.heap!==undefined)document.getElementById('i_heap').textContent=(d.heap/1024).toFixed(0)+' KB';
if(d.tsl!==undefined)document.getElementById('i_tsl').textContent=d.tsl?'OK':'N/A';
if(d.as7!==undefined)document.getElementById('i_as7').textContent=d.as7?'OK':'N/A';
if(d.aht!==undefined)document.getElementById('i_aht').textContent=d.aht?'OK':'N/A';
if(d.gps_ok!==undefined)document.getElementById('i_gps').textContent=d.gps_ok?'Fix':'No fix';
// Equipment (full schema)
if(d.equipment){const eq=d.equipment;let h='';
if(eq.setups&&eq.setups.length){h+='<div style="color:#ffbb00;font-weight:bold;font-size:.8em;margin-bottom:4px">SETUP CONFIGURATI</div>';
eq.setups.forEach(s=>{h+=`<div style="background:#0d1117;border-radius:4px;padding:6px;margin-bottom:4px;font-size:.75em">
<span style="color:#55aaff;font-weight:bold">${s.name||s.id}</span>
${s.description?'<br><span style="color:#8b949e">'+s.description+'</span>':''}
<br><span style="color:#8b949e">Telescopio:</span> ${s.telescope||'--'}
<span style="color:#8b949e">Camera:</span> ${s.camera||'--'}
<span style="color:#8b949e">Montatura:</span> ${s.mount||'--'}
${s.filters?'<br><span style="color:#8b949e">Filtri:</span> '+s.filters:''}
${s.max_wind_kmh?'<br><span style="color:#8b949e">Vento max:</span> '+s.max_wind_kmh+'km/h':''}
${s.use?'<br><span style="color:#8b949e">Uso:</span> '+s.use:''}
</div>`})}
const cats=[['telescopes','Telescopi'],['cameras','Camere'],['mounts','Montature'],['filters','Filtri'],['optical_accessories','Ottici'],['thermal_accessories','Termici'],['power','Alimentazione'],['eyepieces','Oculari']];
cats.forEach(([k,l])=>{if(eq[k]&&eq[k].length){h+=`<div style="color:#8b949e;font-size:.7em;margin-top:6px">${l}: `;
h+=eq[k].map(i=>i.name||i.id).join(', ');h+='</div>'}});
if(h)document.getElementById('d_equip').innerHTML=h}
}catch(e){console.error(e)}
}

// Equipment category system
let eqData={telescopes:[],cameras:[],mounts:[],filters:[],optical_accessories:[],thermal_accessories:[],power:[],eyepieces:[],setups:[]};
let curCat='telescopes';
const catFields={
telescopes:{fields:[['id','ID*'],['name','Nome*'],['type','Tipo*','newton|apo|sc|rc|mak|achro'],['brand','Marca'],['model','Modello'],['aperture_mm','Apertura mm*','n'],['focal_length_mm','Focale mm*','n'],['focal_ratio','F/ratio','n'],['weight_kg','Peso kg','n'],['use','Uso','imaging|visual|both'],['notes','Note']]},
cameras:{fields:[['id','ID*'],['name','Nome*'],['type','Tipo*','cmos_cooled|cmos_uncooled|ccd|dslr|planetary'],['brand','Marca'],['model','Modello'],['sensor','Sensore'],['pixel_size_um','Pixel um*','n'],['resolution_x','Ris X','n'],['resolution_y','Ris Y','n'],['sensor_width_mm','Larg mm','n'],['sensor_height_mm','Alt mm','n'],['cooling','Raffredd.','bool'],['color','Colore','color|mono'],['use','Uso*','imaging|guide|planetary'],['notes','Note']]},
mounts:{fields:[['id','ID*'],['name','Nome*'],['type','Tipo*','eq_goto|eq_manual|altaz_goto|star_tracker'],['brand','Marca'],['model','Modello'],['payload_kg','Carico kg*','n'],['weight_kg','Peso kg','n'],['pe_arcsec','PE arcsec','n'],['goto','GoTo','bool'],['autoguide_port','Porta guida'],['wind_tolerance_kmh','Vento max kmh','n'],['notes','Note']]},
filters:{fields:[['id','ID*'],['name','Nome*'],['type','Tipo*','broadband|narrowband|luminance|rgb|uv_ir_cut'],['brand','Marca'],['model','Modello'],['bandwidth_nm','BW nm','n'],['wavelength_nm','Lambda nm','n'],['line','Linea','ha|oiii|sii|lum|rgb'],['size_mm','Dim mm','n'],['anti_lp','Anti-LP','bool'],['notes','Note']]},
optical_accessories:{fields:[['id','ID*'],['name','Nome*'],['type','Tipo*','coma_corrector|flattener|focal_reducer|barlow|guidescope|finder'],['brand','Marca'],['model','Modello'],['factor','Fattore','n'],['focal_length_mm','Focale mm','n'],['notes','Note']]},
thermal_accessories:{fields:[['id','ID*'],['name','Nome*'],['type','Tipo*','dew_heater|dew_controller|shield|cover'],['brand','Marca'],['for_diameter_mm','Diam mm','n'],['power_w','Potenza W','n'],['notes','Note']]},
power:{fields:[['id','ID*'],['name','Nome*'],['type','Tipo*','battery|power_tank|ac_adapter|solar_panel'],['capacity_wh','Capacita Wh','n'],['voltage_v','Tensione V','n'],['notes','Note']]},
eyepieces:{fields:[['id','ID*'],['name','Nome'],['brand','Marca'],['focal_length_mm','Focale mm*','n'],['afov_deg','AFOV deg','n'],['barrel_mm','Barilotto mm','n'],['notes','Note']]},
setups:{fields:[['id','ID*'],['name','Nome*'],['description','Descrizione'],['telescope','Telescopio','@telescopes'],['camera','Camera','@cameras'],['mount','Montatura','@mounts'],['guide_camera','Camera guida','@cameras'],['guidescope','Guidescope','@optical_accessories'],['filters','Filtri','@filters_multi'],['accessories','Accessori','@optical_accessories_multi'],['thermal','Termico','@thermal_accessories_multi'],['use','Uso','imaging|visual|planetary|widefield|narrowband'],['min_seeing_arcsec','Seeing min','n'],['max_wind_kmh','Vento max kmh','n'],['ideal_bortle_max','Bortle max','n'],['notes','Note']]}
};
function showCat(c){curCat=c;
document.querySelectorAll('#eq_cats .eq-tab').forEach(t=>t.classList.remove('active'));
const idx={telescopes:0,cameras:1,mounts:2,filters:3,optical_accessories:4,thermal_accessories:5,power:6,eyepieces:7,setups:8};
const tabs=document.querySelectorAll('#eq_cats .eq-tab');if(tabs[idx[c]])tabs[idx[c]].classList.add('active');
renderCat()}
function renderCat(){const el=document.getElementById('eq_content');const items=eqData[curCat]||[];
if(!items.length){el.innerHTML='<div style="color:#556677;font-size:.8em;padding:8px">Nessun elemento. Premi + per aggiungere.</div>';return}
let h='';items.forEach((item,idx)=>{
h+='<div style="background:#0d1117;border-radius:4px;padding:8px;margin-bottom:6px;position:relative">';
h+='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
h+='<span style="color:#55aaff;font-weight:bold;font-size:.85em">'+(item.name||item.id||'#'+(idx+1))+'</span>';
h+='<span style="color:#ff3333;cursor:pointer;font-size:.8em" onclick="removeItem('+idx+')">Elimina</span></div>';
const cf=catFields[curCat];if(cf){cf.fields.forEach(f=>{const[k,lbl,opt]=f;
h+='<label style="font-size:.7em">'+lbl+'</label>';
const ss='width:100%;padding:4px;background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;font-size:.8em;margin-bottom:2px';
if(opt&&opt.startsWith('@')){const multi=opt.endsWith('_multi');const src=opt.replace('@','').replace('_multi','');
const srcItems=eqData[src]||[];
if(multi){const sel=(item[k]||'').split(',').filter(s=>s);
h+='<div data-cat="'+curCat+'" data-idx="'+idx+'" data-key="'+k+'" style="'+ss+';min-height:28px;cursor:pointer" onclick="toggleMulti(this,\''+src+'\')">';
if(sel.length){sel.forEach(s=>{const found=srcItems.find(i=>i.id===s);h+='<span style="background:#1f6feb;padding:1px 5px;border-radius:3px;margin:1px;display:inline-block;font-size:.75em">'+(found?found.name||s:s)+'</span>'})}
else{h+='<span style="color:#556677">-- seleziona --</span>'}h+='</div>'}
else{h+='<select data-cat="'+curCat+'" data-idx="'+idx+'" data-key="'+k+'" style="'+ss+'" onchange="updItem(this)"><option value="">--</option>';
srcItems.forEach(si=>{h+='<option value="'+si.id+'"'+(item[k]===si.id?' selected':'')+'>'+(si.name||si.id)+'</option>'});h+='</select>'}}
else if(opt==='bool'){h+='<select data-cat="'+curCat+'" data-idx="'+idx+'" data-key="'+k+'" style="'+ss+'" onchange="updItem(this)"><option value=""'+(item[k]?'':' selected')+'>--</option><option value="true"'+(item[k]===true?' selected':'')+'>Si</option><option value="false"'+(item[k]===false?' selected':'')+'>No</option></select>'}
else if(opt&&opt.includes('|')&&opt!=='n'){const opts=opt.split('|');
h+='<select data-cat="'+curCat+'" data-idx="'+idx+'" data-key="'+k+'" style="'+ss+'" onchange="updItem(this)"><option value="">--</option>';
opts.forEach(o=>{h+='<option value="'+o+'"'+(item[k]===o?' selected':'')+'>'+o+'</option>'});h+='</select>'}
else{h+='<input type="'+(opt==='n'?'number':'text')+'" data-cat="'+curCat+'" data-idx="'+idx+'" data-key="'+k+'" value="'+(item[k]!==undefined?item[k]:'')+'" style="font-size:.8em;padding:4px;margin-bottom:2px" onchange="updItem(this)"'+(opt==='n'?' step="any"':'')+'>'}})}
h+='</div>'});el.innerHTML=h}
function updItem(el){const c=el.dataset.cat,i=parseInt(el.dataset.idx),k=el.dataset.key;
let v=el.value;if(el.type==='number'&&v)v=parseFloat(v);
if(el.tagName==='SELECT'&&(v==='true'||v==='false'))v=v==='true';
if(v===''||v===undefined)delete eqData[c][i][k];else eqData[c][i][k]=v}
function addItem(){if(!eqData[curCat])eqData[curCat]=[];
const id=curCat.substring(0,3)+(eqData[curCat].length+1);
eqData[curCat].push({id:id});renderCat()}
function removeItem(idx){eqData[curCat].splice(idx,1);renderCat()}
function toggleMulti(el,src){const c=el.dataset.cat,i=parseInt(el.dataset.idx),k=el.dataset.key;
const srcItems=eqData[src]||[];if(!srcItems.length){alert('Nessun '+src+' inserito. Aggiungili prima.');return}
const cur=(eqData[c][i][k]||'').split(',').filter(s=>s);
let html='<div style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#161b22;border:2px solid #55aaff;border-radius:8px;padding:12px;z-index:100;min-width:200px;max-height:60vh;overflow-y:auto">';
html+='<div style="font-size:.85em;color:#55aaff;margin-bottom:8px;font-weight:bold">Seleziona '+k+'</div>';
srcItems.forEach(si=>{const checked=cur.includes(si.id);
html+='<label style="display:flex;align-items:center;gap:6px;padding:4px;cursor:pointer;font-size:.8em"><input type="checkbox" value="'+si.id+'"'+(checked?' checked':'')+' style="accent-color:#55aaff">'+(si.name||si.id)+'</label>'});
html+='<button style="width:100%;margin-top:8px;padding:6px;background:#238636;border:none;border-radius:4px;color:#fff;cursor:pointer" onclick="applyMulti(this,\''+c+'\','+i+',\''+k+'\')">OK</button></div>';
html+='<div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:99" onclick="this.parentElement.remove()"></div>';
const d=document.createElement('div');d.innerHTML=html;document.body.appendChild(d)}
function applyMulti(btn,c,i,k){const checks=btn.parentElement.querySelectorAll('input[type=checkbox]:checked');
const vals=Array.from(checks).map(cb=>cb.value).join(',');
if(vals)eqData[c][i][k]=vals;else delete eqData[c][i][k];
btn.parentElement.parentElement.remove();renderCat()}

const defaultEq={
telescopes:[
{id:'ts1',name:'Newton 200/800',type:'newton',brand:'GSO',model:'200/800',aperture_mm:200,focal_length_mm:800,focal_ratio:4,weight_kg:9,use:'imaging'},
{id:'ts2',name:'APO 80/480',type:'apo',brand:'WO',model:'GT81',aperture_mm:80,focal_length_mm:480,focal_ratio:6,weight_kg:3.2,use:'both'}
],cameras:[
{id:'cam1',name:'ASI294MC Pro',type:'cmos_cooled',brand:'ZWO',model:'ASI294MC Pro',sensor:'IMX294',pixel_size_um:4.63,resolution_x:4144,resolution_y:2822,sensor_width_mm:19.2,sensor_height_mm:13.1,cooling:true,color:'color',use:'imaging'},
{id:'cam2',name:'ASI120MM Mini',type:'planetary',brand:'ZWO',model:'ASI120MM Mini',sensor:'AR0130',pixel_size_um:3.75,resolution_x:1280,resolution_y:960,cooling:false,color:'mono',use:'guide'}
],mounts:[
{id:'mnt1',name:'HEQ5 Pro',type:'eq_goto',brand:'SkyWatcher',model:'HEQ5 Pro',payload_kg:15,weight_kg:10,pe_arcsec:8,goto:true,autoguide_port:'ST4',wind_tolerance_kmh:20}
],filters:[
{id:'f1',name:'L-Pro',type:'broadband',brand:'Optolong',model:'L-Pro',bandwidth_nm:400,anti_lp:true},
{id:'f2',name:'L-eNhance',type:'narrowband',brand:'Optolong',model:'L-eNhance',bandwidth_nm:24,line:'ha',anti_lp:true},
{id:'f3',name:'UV/IR Cut',type:'uv_ir_cut',brand:'ZWO',model:'UV/IR Cut'}
],optical_accessories:[
{id:'oa1',name:'Correttore coma GPU',type:'coma_corrector',brand:'GPU',model:'Coma corrector',factor:1.0},
{id:'oa2',name:'Guidescope 30mm',type:'guidescope',brand:'ZWO',model:'30/120',focal_length_mm:120}
],thermal_accessories:[
{id:'th1',name:'Fascia anticondensa 200mm',type:'dew_heater',brand:'Generic',for_diameter_mm:200,power_w:12}
],power:[
{id:'pw1',name:'Batteria 12V 20Ah',type:'battery',capacity_wh:240,voltage_v:12}
],eyepieces:[],
setups:[
{id:'setup1',name:'Deep Sky Widefield',description:'Newton 200 + ASI294 su HEQ5 guidata',telescope:'ts1',camera:'cam1',mount:'mnt1',guide_camera:'cam2',guidescope:'oa2',filters:'f1,f2',accessories:'oa1',thermal:'th1',use:'imaging',max_wind_kmh:20,ideal_bortle_max:5}
]};

async function loadConfig(){
try{const r=await fetch('/api/config');const d=await r.json();
if(d.owm_key)document.getElementById('c_owm').value=d.owm_key;
if(d.n2yo_key)document.getElementById('c_n2yo').value=d.n2yo_key;
if(d.google_key)document.getElementById('c_google').value=d.google_key;
if(d.fallback_lat)document.getElementById('c_lat').value=d.fallback_lat;
if(d.fallback_lon)document.getElementById('c_lon').value=d.fallback_lon;
if(d.sqm_server_url)document.getElementById('c_sqm_url').value=d.sqm_server_url;
if(d.sqm_api_key)document.getElementById('c_sqm_key').value=d.sqm_api_key;
if(d.sqm_privacy)document.getElementById('c_sqm_privacy').checked=true;
if(d.alpaca_url)document.getElementById('c_alpaca').value=d.alpaca_url;
if(d.nina_url)document.getElementById('c_nina').value=d.nina_url;
if(d.phd2_url)document.getElementById('c_phd2').value=d.phd2_url;
if(d.stellarium_url)document.getElementById('c_stellarium').value=d.stellarium_url;
if(d.indi_url)document.getElementById('c_indi').value=d.indi_url;
if(d.dew_gpio!==undefined)document.getElementById('c_dew_gpio').value=d.dew_gpio;
if(d.dew_threshold!==undefined)document.getElementById('c_dew_thr').value=d.dew_threshold;
if(d.temp_offset!==undefined)document.getElementById('c_temp_off').value=d.temp_offset;
if(d.hum_offset!==undefined)document.getElementById('c_hum_off').value=d.hum_offset;
if(d.lux_threshold!==undefined)document.getElementById('c_lux_thr').value=d.lux_threshold;
if(d.night_threshold!==undefined)document.getElementById('c_night_thr').value=d.night_threshold;
if(d.equipment&&Object.keys(d.equipment).some(k=>d.equipment[k]&&d.equipment[k].length)){eqData=Object.assign(eqData,d.equipment)}
else{eqData=JSON.parse(JSON.stringify(defaultEq))}
renderCat();
}catch(e){}}

async function saveConfig(){
const body={
owm_key:document.getElementById('c_owm').value,
n2yo_key:document.getElementById('c_n2yo').value,
google_key:document.getElementById('c_google').value,
fallback_lat:parseFloat(document.getElementById('c_lat').value)||0,
fallback_lon:parseFloat(document.getElementById('c_lon').value)||0,
sqm_server_url:document.getElementById('c_sqm_url').value,
sqm_api_key:document.getElementById('c_sqm_key').value,
sqm_privacy:document.getElementById('c_sqm_privacy').checked,
alpaca_url:document.getElementById('c_alpaca').value,
nina_url:document.getElementById('c_nina').value,
phd2_url:document.getElementById('c_phd2').value,
stellarium_url:document.getElementById('c_stellarium').value,
indi_url:document.getElementById('c_indi').value,
dew_gpio:parseInt(document.getElementById('c_dew_gpio').value)||-1,
dew_threshold:parseFloat(document.getElementById('c_dew_thr').value)||3.0,
temp_offset:parseFloat(document.getElementById('c_temp_off').value)||0,
hum_offset:parseFloat(document.getElementById('c_hum_off').value)||0,
lux_threshold:parseFloat(document.getElementById('c_lux_thr').value)||1.0,
night_threshold:parseFloat(document.getElementById('c_night_thr').value)||10.0,
equipment:eqData
};
try{const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
if(r.ok)showMsg('Configurazione salvata!',true);else showMsg('Errore',false);
}catch(e){showMsg('Errore di connessione',false)}}

// Comandi AI
function toggleAcc(el){const body=el.nextElementSibling;
const open=body.style.display==='flex';
body.style.display=open?'none':'flex';
el.classList.toggle('open',!open)}

let cmdRecents=JSON.parse(localStorage.getItem('sg_cmd_recent')||'[]');
function renderRecents(){const el=document.getElementById('cmdRecentList');
const wrap=document.getElementById('cmdRecent');
if(!cmdRecents.length){wrap.style.display='none';return}
wrap.style.display='block';
el.innerHTML=cmdRecents.slice(0,8).map(c=>'<button class="rbtn" onclick="sendCmd(\''+c.replace(/'/g,"\\'")+'\')">'+c.substring(0,30)+(c.length>30?'...':'')+'</button>').join('')}

async function sendCmd(text){
const dot=document.getElementById('cmdDot');
const state=document.getElementById('cmdState');
const resp=document.getElementById('cmdResponse');
const respText=document.getElementById('cmdRespText');
dot.style.background='#ffbb00';state.textContent='Invio...';
try{
const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text})});
const d=await r.json();
if(d.ok){dot.style.background='#00dd66';state.textContent='Inviato: '+text.substring(0,40);
resp.style.display='block';respText.textContent='Comando inviato a Sophia. La risposta arrivera via voce dal dispositivo.';
// Save to recents
cmdRecents=cmdRecents.filter(c=>c!==text);cmdRecents.unshift(text);
if(cmdRecents.length>8)cmdRecents.pop();
localStorage.setItem('sg_cmd_recent',JSON.stringify(cmdRecents));renderRecents();
setTimeout(()=>{dot.style.background='#00dd66';state.textContent='Pronto'},5000)}
else{dot.style.background='#ff3333';state.textContent='Errore';resp.style.display='block';respText.textContent='Errore invio comando'}
}catch(e){dot.style.background='#ff3333';state.textContent='Errore connessione';
resp.style.display='block';respText.textContent='Impossibile contattare il dispositivo'}}

loadStatus();loadConfig();renderCat();renderRecents();
setInterval(loadStatus,3000);
</script>
</body>
</html>)rawhtml";

// =========================================================================
// HTTP Handlers
// =========================================================================

esp_err_t SkyGuardWebUI::HandleRoot(httpd_req_t* req) {
    httpd_resp_set_type(req, "text/html");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache");
    return httpd_resp_send(req, WEBUI_HTML, sizeof(WEBUI_HTML) - 1);
}

esp_err_t SkyGuardWebUI::HandleGetStatus(httpd_req_t* req) {
    auto* self = (SkyGuardWebUI*)req->user_ctx;

    if (self && self->status_fn_) {
        std::string json = self->status_fn_(self->status_ctx_);
        httpd_resp_set_type(req, "application/json");
        return httpd_resp_send(req, json.c_str(), json.length());
    }

    // Fallback: minimal status
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, "{}", 2);
}

esp_err_t SkyGuardWebUI::HandleGetConfig(httpd_req_t* req) {
    Settings s("skyguard", false);
    std::string owm = s.GetString("owm_key", "");
    std::string n2yo = s.GetString("n2yo_key", "");
    std::string google = s.GetString("google_key", "");
    std::string sqm_url = s.GetString("sqm_server_url", "");
    std::string lat_str = s.GetString("fallback_lat", "44.9019");
    std::string lon_str = s.GetString("fallback_lon", "8.1662");
    float fb_lat = std::strtof(lat_str.c_str(), nullptr);
    float fb_lon = std::strtof(lon_str.c_str(), nullptr);

    auto mask = [](const std::string& key) -> std::string {
        if (key.length() <= 4) return key;
        return std::string(key.length() - 4, '*') + key.substr(key.length() - 4);
    };

    cJSON* root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "owm_key", owm.empty() ? "" : mask(owm).c_str());
    cJSON_AddStringToObject(root, "n2yo_key", n2yo.empty() ? "" : mask(n2yo).c_str());
    cJSON_AddStringToObject(root, "google_key", google.empty() ? "" : mask(google).c_str());
    cJSON_AddStringToObject(root, "sqm_server_url", sqm_url.c_str());
    std::string sqm_key = s.GetString("sqm_api_key", "");
    cJSON_AddStringToObject(root, "sqm_api_key", sqm_key.empty() ? "" : mask(sqm_key).c_str());
    std::string privacy_str = s.GetString("sqm_privacy", "0");
    cJSON_AddBoolToObject(root, "sqm_privacy", privacy_str == "1");
    cJSON_AddNumberToObject(root, "fallback_lat", fb_lat);
    cJSON_AddNumberToObject(root, "fallback_lon", fb_lon);

    // Remote control URLs
    std::string alpaca_url = s.GetString("alpaca_url", "");
    cJSON_AddStringToObject(root, "alpaca_url", alpaca_url.c_str());
    std::string nina_url = s.GetString("nina_url", "");
    cJSON_AddStringToObject(root, "nina_url", nina_url.c_str());
    std::string phd2_url = s.GetString("phd2_url", "");
    cJSON_AddStringToObject(root, "phd2_url", phd2_url.c_str());
    std::string stellarium_url = s.GetString("stellarium_url", "");
    cJSON_AddStringToObject(root, "stellarium_url", stellarium_url.c_str());
    std::string indi_url = s.GetString("indi_url", "");
    cJSON_AddStringToObject(root, "indi_url", indi_url.c_str());

    // Dew heater
    cJSON_AddNumberToObject(root, "dew_gpio", s.GetInt("dew_gpio", -1));
    std::string dew_thr = s.GetString("dew_threshold", "3.0");
    cJSON_AddNumberToObject(root, "dew_threshold", std::strtof(dew_thr.c_str(), nullptr));

    // Calibration
    std::string temp_off_str = s.GetString("temp_offset", "-2.4");
    std::string hum_off_str = s.GetString("hum_offset", "0");
    std::string lux_thr_str = s.GetString("lux_threshold", "1.0");
    std::string night_thr_str = s.GetString("night_threshold", "10.0");
    cJSON_AddNumberToObject(root, "temp_offset", std::strtof(temp_off_str.c_str(), nullptr));
    cJSON_AddNumberToObject(root, "hum_offset", std::strtof(hum_off_str.c_str(), nullptr));
    cJSON_AddNumberToObject(root, "lux_threshold", std::strtof(lux_thr_str.c_str(), nullptr));
    cJSON_AddNumberToObject(root, "night_threshold", std::strtof(night_thr_str.c_str(), nullptr));

    // Equipment (stored as single JSON blob in NVS key "equipment")
    std::string eq_json = s.GetString("equipment", "");
    if (!eq_json.empty()) {
        cJSON* eq = cJSON_Parse(eq_json.c_str());
        if (eq) {
            cJSON_AddItemToObject(root, "equipment", eq);
        }
    }

    char* json = cJSON_PrintUnformatted(root);
    httpd_resp_set_type(req, "application/json");
    esp_err_t ret = httpd_resp_send(req, json, strlen(json));
    free(json);
    cJSON_Delete(root);
    return ret;
}

esp_err_t SkyGuardWebUI::HandlePostConfig(httpd_req_t* req) {
    // Use content_len to allocate proper buffer (equipment JSON can be large)
    size_t content_len = req->content_len;
    if (content_len == 0 || content_len > 16384) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid content length");
        return ESP_FAIL;
    }

    char* buf = (char*)heap_caps_malloc(content_len + 1, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!buf) {
        buf = (char*)malloc(content_len + 1);
    }
    if (!buf) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "OOM");
        return ESP_FAIL;
    }

    // Read full body (may require multiple recv calls)
    size_t total = 0;
    while (total < content_len) {
        int received = httpd_req_recv(req, buf + total, content_len - total);
        if (received <= 0) {
            free(buf);
            httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Recv failed");
            return ESP_FAIL;
        }
        total += received;
    }
    buf[total] = '\0';

    cJSON* root = cJSON_Parse(buf);
    free(buf);
    if (!root) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON");
        return ESP_FAIL;
    }

    Settings s("skyguard", true);

    auto saveKey = [&](const char* json_field, const char* nvs_key) {
        cJSON* item = cJSON_GetObjectItem(root, json_field);
        if (item && item->valuestring && item->valuestring[0] != '*' && item->valuestring[0] != '\0') {
            s.SetString(nvs_key, item->valuestring);
            ESP_LOGI(TAG, "%s saved", nvs_key);
        }
    };

    saveKey("owm_key", "owm_key");
    saveKey("n2yo_key", "n2yo_key");
    saveKey("google_key", "google_key");
    saveKey("sqm_server_url", "sqm_server_url");
    saveKey("sqm_api_key", "sqm_api_key");

    // Privacy flag (boolean → stored as "0"/"1")
    cJSON* privacy_item = cJSON_GetObjectItem(root, "sqm_privacy");
    if (privacy_item) {
        s.SetString("sqm_privacy", cJSON_IsTrue(privacy_item) ? "1" : "0");
    }

    cJSON* lat = cJSON_GetObjectItem(root, "fallback_lat");
    if (lat && cJSON_IsNumber(lat) && lat->valuedouble != 0) {
        char buf[16];
        snprintf(buf, sizeof(buf), "%.6f", lat->valuedouble);
        s.SetString("fallback_lat", buf);
    }
    cJSON* lon = cJSON_GetObjectItem(root, "fallback_lon");
    if (lon && cJSON_IsNumber(lon) && lon->valuedouble != 0) {
        char buf[16];
        snprintf(buf, sizeof(buf), "%.6f", lon->valuedouble);
        s.SetString("fallback_lon", buf);
    }

    // Remote control URLs
    saveKey("alpaca_url", "alpaca_url");
    saveKey("nina_url", "nina_url");
    saveKey("phd2_url", "phd2_url");
    saveKey("stellarium_url", "stellarium_url");
    saveKey("indi_url", "indi_url");

    // Dew heater config
    cJSON* dew_gpio_item = cJSON_GetObjectItem(root, "dew_gpio");
    if (dew_gpio_item && cJSON_IsNumber(dew_gpio_item)) {
        s.SetInt("dew_gpio", (int)dew_gpio_item->valuedouble);
    }
    auto saveDewFloat = [&](const char* json_field, const char* nvs_key) {
        cJSON* item = cJSON_GetObjectItem(root, json_field);
        if (item && cJSON_IsNumber(item)) {
            char buf[16];
            snprintf(buf, sizeof(buf), "%.1f", item->valuedouble);
            s.SetString(nvs_key, buf);
        }
    };
    saveDewFloat("dew_threshold", "dew_threshold");

    // Calibration values
    auto saveFloat = [&](const char* json_field, const char* nvs_key) {
        cJSON* item = cJSON_GetObjectItem(root, json_field);
        if (item && cJSON_IsNumber(item)) {
            char buf[16];
            snprintf(buf, sizeof(buf), "%.2f", item->valuedouble);
            s.SetString(nvs_key, buf);
        }
    };
    saveFloat("temp_offset", "temp_offset");
    saveFloat("hum_offset", "hum_offset");
    saveFloat("lux_threshold", "lux_threshold");
    saveFloat("night_threshold", "night_threshold");

    // Equipment — store as single JSON blob
    cJSON* eq = cJSON_GetObjectItem(root, "equipment");
    if (eq && cJSON_IsObject(eq)) {
        char* eq_str = cJSON_PrintUnformatted(eq);
        if (eq_str) {
            s.SetString("equipment", eq_str);
            ESP_LOGI(TAG, "Equipment saved (%d bytes)", (int)strlen(eq_str));
            free(eq_str);
        }
    }

    cJSON_Delete(root);

    // Notify board to reload config from NVS
    auto* self = (SkyGuardWebUI*)req->user_ctx;
    if (self && self->config_saved_fn_) {
        self->config_saved_fn_(self->config_saved_ctx_);
    }

    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, "{\"ok\":true}", 11);
}

esp_err_t SkyGuardWebUI::HandlePostCommand(httpd_req_t* req) {
    size_t content_len = req->content_len;
    if (content_len == 0 || content_len > 1024) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid length");
        return ESP_FAIL;
    }

    char buf[1025];
    int received = httpd_req_recv(req, buf, content_len);
    if (received <= 0) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Recv failed");
        return ESP_FAIL;
    }
    buf[received] = '\0';

    cJSON* root = cJSON_Parse(buf);
    if (!root) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid JSON");
        return ESP_FAIL;
    }

    cJSON* text_item = cJSON_GetObjectItem(root, "text");
    if (!text_item || !cJSON_IsString(text_item) || !text_item->valuestring[0]) {
        cJSON_Delete(root);
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Missing text");
        return ESP_FAIL;
    }

    std::string text = text_item->valuestring;
    cJSON_Delete(root);

    ESP_LOGI(TAG, "AI command from WebUI: %s", text.c_str());
    Application::GetInstance().SendChatMessage(text);

    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, "{\"ok\":true}", 11);
}

// =========================================================================
// Server lifecycle
// =========================================================================

SkyGuardWebUI::SkyGuardWebUI() {}

SkyGuardWebUI::~SkyGuardWebUI() {
    Stop();
}

void SkyGuardWebUI::Start() {
    if (server_) return;

    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.max_uri_handlers = 10;
    config.uri_match_fn = httpd_uri_match_wildcard;
    config.lru_purge_enable = true;
    config.stack_size = 8192;

    ESP_LOGI(TAG, "Starting WebUI on port 80...");
    esp_err_t err = httpd_start(&server_, &config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server: %s", esp_err_to_name(err));
        return;
    }

    httpd_uri_t root_uri = { .uri = "/", .method = HTTP_GET, .handler = HandleRoot, .user_ctx = this };
    httpd_uri_t status_uri = { .uri = "/api/status", .method = HTTP_GET, .handler = HandleGetStatus, .user_ctx = this };
    httpd_uri_t get_config = { .uri = "/api/config", .method = HTTP_GET, .handler = HandleGetConfig, .user_ctx = this };
    httpd_uri_t post_config = { .uri = "/api/config", .method = HTTP_POST, .handler = HandlePostConfig, .user_ctx = this };

    httpd_uri_t post_cmd = { .uri = "/api/command", .method = HTTP_POST, .handler = HandlePostCommand, .user_ctx = this };

    httpd_register_uri_handler(server_, &root_uri);
    httpd_register_uri_handler(server_, &status_uri);
    httpd_register_uri_handler(server_, &get_config);
    httpd_register_uri_handler(server_, &post_config);
    httpd_register_uri_handler(server_, &post_cmd);

    ESP_LOGI(TAG, "WebUI started");
}

void SkyGuardWebUI::Stop() {
    if (server_) {
        httpd_stop(server_);
        server_ = nullptr;
    }
}
