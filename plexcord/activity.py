import asyncio
import contextlib
import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict

from aiohttp import WSMsgType, web

from .plex import PlexError, Track, valid_url
from .store import UserLink

ACTIVITY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#07080d">
<link rel="icon" type="image/jpeg" href="/api/logo">
<title>Plexcord</title>
<style>
:root{
  --bg:#08090c;
  --bg-2:#0e1015;
  --surface:rgba(20,22,29,.72);
  --surface-2:rgba(255,255,255,.045);
  --surface-3:rgba(255,255,255,.085);
  --border:rgba(255,255,255,.065);
  --border-hi:rgba(255,255,255,.14);
  --text:#f4f5f8;
  --text-2:#c3c8d4;
  --text-dim:#8a91a2;
  --accent:#e5a00d;
  --accent-hi:#ffbe3d;
  --accent-ink:#1a1204;
  --accent-soft:rgba(229,160,13,.14);
  --blurple:#5865f2;
  --blurple-hi:#7983ff;
  --blurple-soft:rgba(88,101,242,.16);
  --ok:#2dc26b;
  --danger:#f0565b;
  --radius-xl:24px;
  --radius-lg:18px;
  --radius-md:13px;
  --radius-sm:10px;
  --ease:cubic-bezier(.22,.8,.26,1);
  --safe-top:env(safe-area-inset-top,0px);
  --safe-bottom:env(safe-area-inset-bottom,0px);
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{
  width:100%;height:100%;height:100dvh;overflow:hidden;
  background:var(--bg);color:var(--text);
  font-family:"Inter","SF Pro Display",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-feature-settings:"cv11","ss01";
  user-select:none;-webkit-font-smoothing:antialiased;
}
body{display:flex;flex-direction:column;position:relative}
svg{width:16px;height:16px;fill:currentColor;flex-shrink:0;display:block}
b{font-weight:700;color:var(--text)}
code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.92em;background:var(--surface-3);padding:1px 5px;border-radius:5px}

/* Sfondo ambientale generato dalla copertina */
#ambient-bg{
  position:fixed;inset:-15%;
  background-size:cover;background-position:center;
  filter:blur(90px) saturate(1.6) brightness(.42);
  transform:scale(1.1);
  opacity:0;transition:opacity 1.2s var(--ease),background-image 1s ease;
  pointer-events:none;z-index:0;
}
#ambient-grad{
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background:
    radial-gradient(1200px 600px at 0% 0%,rgba(229,160,13,.09),transparent 60%),
    radial-gradient(900px 600px at 100% 100%,rgba(88,101,242,.10),transparent 60%),
    linear-gradient(180deg,rgba(8,9,12,.25),rgba(8,9,12,.85));
}

/* Topbar */
header{
  position:relative;z-index:10;
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:calc(12px + var(--safe-top)) 18px 12px;
  flex-shrink:0;
}
.brand{display:flex;align-items:center;gap:11px;min-width:0;flex:1}
.logo-mark{
  width:34px;height:34px;border-radius:11px;flex-shrink:0;
  background:conic-gradient(from 200deg,var(--accent),#ff7a18,var(--blurple),var(--accent));
  display:inline-flex;align-items:center;justify-content:center;color:#fff;
  box-shadow:0 6px 20px rgba(229,160,13,.28),inset 0 1px 0 rgba(255,255,255,.35);
  overflow:hidden;
}
.logo-mark svg{width:18px;height:18px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))}
.brand-title{font-weight:800;font-size:16px;letter-spacing:-.3px}
.header-meta{display:flex;align-items:center;gap:6px;min-width:0;overflow:hidden}
.header-right{display:flex;align-items:center;gap:7px;flex-shrink:0}

.badge{
  font-size:11px;font-weight:600;letter-spacing:.1px;
  padding:5px 11px;border-radius:99px;
  background:var(--surface-2);border:1px solid var(--border);color:var(--text-2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  display:inline-flex;align-items:center;gap:6px;max-width:200px;
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
}
.badge.mode-act{background:var(--blurple-soft);border-color:rgba(88,101,242,.3);color:#cdd2ff}
.badge.sync-ok{background:rgba(45,194,107,.12);border-color:rgba(45,194,107,.32);color:#8ff0b6}
.badge.rpc-btn{cursor:pointer;max-width:none;transition:all .2s var(--ease)}
.badge.rpc-btn:hover{background:var(--blurple-soft);border-color:rgba(88,101,242,.45);color:#fff;transform:translateY(-1px)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--text-dim);flex-shrink:0}
.dot.live{background:var(--ok);box-shadow:0 0 0 0 rgba(45,194,107,.6);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(45,194,107,.55)}70%{box-shadow:0 0 0 7px rgba(45,194,107,0)}100%{box-shadow:0 0 0 0 rgba(45,194,107,0)}}

/* Layout */
main{
  position:relative;z-index:2;
  display:grid;grid-template-columns:clamp(280px,30vw,340px) 1fr;
  gap:16px;padding:0 18px 18px;
  flex:1;min-height:0;overflow:hidden;
}
.panel{
  background:linear-gradient(180deg,rgba(26,28,36,.74),rgba(16,18,24,.78));
  backdrop-filter:blur(30px) saturate(1.3);-webkit-backdrop-filter:blur(30px) saturate(1.3);
  border:1px solid var(--border);
  border-radius:var(--radius-xl);
  padding:20px;
  display:flex;flex-direction:column;gap:16px;
  min-height:0;overflow:hidden;
  box-shadow:0 30px 60px -20px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.05);
}

/* Player */
#player-panel{justify-content:space-between;position:relative}
.player-sheet-bar{display:none;align-items:center;justify-content:space-between;flex-shrink:0}
.sheet-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:var(--text-dim)}

.now-row{display:flex;flex-direction:column;align-items:center;text-align:center;gap:18px;min-width:0}
.art-wrap{
  width:100%;max-width:236px;aspect-ratio:1/1;flex-shrink:0;
  background:linear-gradient(145deg,#171a23,#262b3a);
  border-radius:20px;overflow:hidden;position:relative;
  display:flex;align-items:center;justify-content:center;color:rgba(255,255,255,.2);
  box-shadow:0 24px 48px -12px rgba(0,0,0,.75),0 0 0 1px rgba(255,255,255,.07);
  transition:transform .5s var(--ease),box-shadow .5s var(--ease);
}
body.is-playing .art-wrap{transform:scale(1.0);box-shadow:0 30px 60px -12px rgba(0,0,0,.8),0 0 0 1px rgba(255,255,255,.09)}
body.is-paused .art-wrap{transform:scale(.94)}
.art-wrap svg{width:56px;height:56px;opacity:.5}
.art-wrap img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;z-index:2;animation:fadein .5s var(--ease)}
@keyframes fadein{from{opacity:0;transform:scale(1.03)}to{opacity:1;transform:none}}
.eq-overlay{
  position:absolute;bottom:10px;right:10px;z-index:3;
  background:rgba(8,9,12,.7);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid var(--border-hi);border-radius:9px;
  padding:5px 7px;display:none;align-items:flex-end;gap:3px;height:24px;
}
.eq-overlay.playing{display:inline-flex}
.eq-bar{width:3px;background:var(--accent-hi);border-radius:2px;animation:eq .8s ease-in-out infinite alternate}
.eq-bar:nth-child(2){animation-delay:.25s}
.eq-bar:nth-child(3){animation-delay:.5s}
@keyframes eq{0%{height:3px}100%{height:13px}}

.now-meta{width:100%;min-width:0;display:flex;flex-direction:column;gap:4px}
.now-title{font-size:18px;font-weight:800;letter-spacing:-.35px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.now-sub{font-size:12px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#now-artist{color:var(--accent-hi);font-weight:600;font-size:13.5px}

/* Avanzamento */
.progress-box{display:flex;flex-direction:column;gap:8px;flex-shrink:0}
.bar{
  width:100%;height:5px;background:rgba(255,255,255,.1);
  border-radius:99px;cursor:pointer;position:relative;
  transition:height .2s var(--ease);
}
.bar::before{content:"";position:absolute;inset:-8px 0}
.bar:hover{height:7px}
.bar-fill{
  height:100%;width:0%;border-radius:99px;position:relative;
  background:linear-gradient(90deg,var(--accent),var(--accent-hi));
  box-shadow:0 0 14px rgba(229,160,13,.45);
  transition:width .25s linear;
}
.bar-fill::after{
  content:"";position:absolute;right:-7px;top:50%;transform:translateY(-50%) scale(0);
  width:14px;height:14px;border-radius:50%;background:#fff;
  box-shadow:0 2px 10px rgba(0,0,0,.6);transition:transform .2s var(--ease);
}
.bar:hover .bar-fill::after{transform:translateY(-50%) scale(1)}
.times{display:flex;justify-content:space-between;font-size:11px;color:var(--text-dim);font-variant-numeric:tabular-nums;font-weight:600}

/* Pulsanti */
button{
  background:var(--surface-2);color:var(--text);
  border:1px solid var(--border);border-radius:var(--radius-sm);
  padding:8px 13px;font-size:12px;font-weight:600;font-family:inherit;
  cursor:pointer;display:inline-flex;align-items:center;justify-content:center;gap:6px;
  transition:background .18s var(--ease),border-color .18s var(--ease),transform .18s var(--ease),box-shadow .18s var(--ease),color .18s;
  white-space:nowrap;
}
button:hover{background:var(--surface-3);border-color:var(--border-hi)}
button:active{transform:scale(.95)}
button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button.primary{
  background:linear-gradient(180deg,var(--accent-hi),var(--accent));
  border-color:rgba(255,255,255,.18);color:var(--accent-ink);
  box-shadow:0 6px 18px -4px rgba(229,160,13,.5),inset 0 1px 0 rgba(255,255,255,.35);
}
button.primary:hover{filter:brightness(1.07);background:linear-gradient(180deg,var(--accent-hi),var(--accent))}
button.ok{
  background:rgba(45,194,107,.14);border-color:rgba(45,194,107,.32);color:#9af3bf;
}
button.ok:hover{background:var(--ok);border-color:var(--ok);color:#04150b}
button.blurple{
  background:linear-gradient(180deg,var(--blurple-hi),var(--blurple));
  border-color:rgba(255,255,255,.16);color:#fff;
  box-shadow:0 6px 18px -4px rgba(88,101,242,.55),inset 0 1px 0 rgba(255,255,255,.25);
}
button.blurple:hover{filter:brightness(1.08);background:linear-gradient(180deg,var(--blurple-hi),var(--blurple))}
button.danger{background:rgba(240,86,91,.1);border-color:rgba(240,86,91,.28);color:#ff9a9d}
button.danger:hover{background:var(--danger);color:#fff;border-color:var(--danger)}
button.icon-btn{width:40px;height:40px;padding:0;border-radius:50%;background:transparent;border-color:transparent;color:var(--text-2)}
button.icon-btn:hover{background:var(--surface-3);color:#fff}
button.icon-btn svg{width:19px;height:19px}

.controls{display:flex;align-items:center;justify-content:center;gap:6px;flex-shrink:0}
#btn-play{
  width:58px;height:58px;padding:0;border-radius:50%;
  box-shadow:0 12px 28px -6px rgba(229,160,13,.6),inset 0 1px 0 rgba(255,255,255,.4);
}
#btn-play svg{width:26px;height:26px}
#btn-play:hover{transform:scale(1.05)}
#btn-play:active{transform:scale(.94)}
#btn-play .btn-play-lbl{display:none}
#btn-skip svg{width:22px;height:22px}
#btn-stop.danger{background:transparent;border-color:transparent;color:#ff9a9d}
#btn-stop.danger:hover{background:rgba(240,86,91,.15)}
#btn-expand-player{display:none}

/* Volume */
.vol-row{display:flex;align-items:center;gap:8px;font-size:11px;color:var(--text-dim);flex-shrink:0}
.vol-btn{width:30px;height:30px;padding:0;border-radius:50%;font-size:14px;background:transparent;border-color:transparent;color:var(--text-dim)}
.vol-btn:hover{color:#fff}
input[type=range]{
  -webkit-appearance:none;appearance:none;flex:1;min-width:60px;height:18px;
  background:transparent;cursor:pointer;
}
input[type=range]::-webkit-slider-runnable-track{height:4px;border-radius:99px;background:linear-gradient(90deg,var(--text-2) var(--fill,66%),rgba(255,255,255,.12) var(--fill,66%))}
input[type=range]::-moz-range-track{height:4px;border-radius:99px;background:rgba(255,255,255,.12)}
input[type=range]::-moz-range-progress{height:4px;border-radius:99px;background:var(--text-2)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;margin-top:-5px;border-radius:50%;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.5);transition:transform .15s}
input[type=range]::-moz-range-thumb{width:14px;height:14px;border:none;border-radius:50%;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.5)}
input[type=range]:hover::-webkit-slider-thumb{transform:scale(1.2)}
#vol-val{min-width:38px;text-align:right;font-weight:700;color:var(--text-2);font-variant-numeric:tabular-nums}
.listeners-pill{
  font-size:11px;color:#9af3bf;font-weight:600;text-align:center;
  background:rgba(45,194,107,.08);border:1px solid rgba(45,194,107,.22);
  padding:7px 11px;border-radius:99px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}

/* Navigazione */
#main-panel{padding:16px 18px;gap:14px}
.tabs{
  display:flex;gap:4px;padding:4px;flex-shrink:0;overflow-x:auto;
  background:rgba(0,0,0,.28);border:1px solid var(--border);border-radius:15px;
}
.tab{
  flex:1;background:transparent;border-color:transparent;color:var(--text-dim);
  padding:9px 12px;border-radius:11px;font-size:12.5px;font-weight:600;gap:7px;
}
.tab:hover{background:var(--surface-2);color:var(--text);transform:none}
.tab.active{background:var(--surface-3);color:#fff;border-color:var(--border-hi);box-shadow:0 4px 14px rgba(0,0,0,.3)}
.tab.active svg{color:var(--accent-hi)}
.tab-count{
  background:var(--accent-soft);color:var(--accent-hi);
  padding:1px 7px;border-radius:99px;font-size:10.5px;font-weight:700;font-variant-numeric:tabular-nums;
}
.view-anim{animation:viewin .28s var(--ease)}
@keyframes viewin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* Input */
.search-bar{display:flex;gap:8px;flex-wrap:wrap;flex-shrink:0}
.search-input-wrap{position:relative;flex:1;min-width:170px;display:flex;align-items:center}
.search-input-wrap svg{position:absolute;left:14px;color:var(--text-dim);pointer-events:none;width:17px;height:17px}
.search-input-wrap input[type=search]{padding-left:40px;width:100%;height:42px;font-size:13.5px;border-radius:13px}
input[type=search],input[type=text],input[type=password],input[type=number],select{
  background:rgba(0,0,0,.3);color:var(--text);
  border:1px solid var(--border);border-radius:var(--radius-sm);
  padding:9px 12px;font-size:12.5px;font-family:inherit;outline:none;min-width:0;
  transition:border-color .18s,box-shadow .18s,background .18s;
}
select{cursor:pointer}
input::placeholder{color:#6b7283}
input[type=search]:focus,input[type=text]:focus,input[type=password]:focus,input[type=number]:focus,select:focus{
  border-color:rgba(229,160,13,.55);background:rgba(0,0,0,.42);box-shadow:0 0 0 4px rgba(229,160,13,.12);
}

/* Liste brani / playlist */
.list{flex:1;overflow-y:auto;overflow-x:hidden;display:flex;flex-direction:column;gap:2px;min-height:0;margin:0 -6px;padding:0 6px}
.item{
  display:flex;align-items:center;gap:13px;padding:7px 8px;
  border-radius:var(--radius-md);flex-shrink:0;border:1px solid transparent;
  transition:background .18s var(--ease),border-color .18s var(--ease);
  animation:rowin .3s var(--ease) both;
}
.item:nth-child(-n+12){animation-delay:calc(var(--i,0) * 18ms)}
@keyframes rowin{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.item:hover{background:var(--surface-2);border-color:var(--border)}
.item.is-current{background:var(--accent-soft);border-color:rgba(229,160,13,.25)}
.item.is-current .item-title{color:var(--accent-hi)}
.item-thumb{
  width:50px;height:50px;min-width:50px;border-radius:10px;
  background:linear-gradient(145deg,#1a1d27,#2a2f3f);
  flex-shrink:0;overflow:hidden;position:relative;
  display:flex;align-items:center;justify-content:center;color:var(--text-dim);
  box-shadow:0 6px 14px -4px rgba(0,0,0,.6),0 0 0 1px rgba(255,255,255,.06);
}
.item-thumb svg{width:20px;height:20px;opacity:.45;position:relative;z-index:1}
.item-thumb img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;z-index:2;animation:fadein .35s var(--ease)}
.item-thumb[data-play]{cursor:pointer}
.item-thumb[data-play]::after{
  content:"";position:absolute;inset:0;z-index:3;opacity:0;transition:opacity .18s;
  background:rgba(0,0,0,.5) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='M8 5v14l11-7z'/%3E%3C/svg%3E") center/22px no-repeat;
}
.item:hover .item-thumb[data-play]::after{opacity:1}
.item-info{min-width:0;flex:1;display:flex;flex-direction:column;gap:2px}
.item-title{font-size:13.5px;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text)}
.item-artist{font-size:12px;font-weight:500;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item-meta{font-size:11px;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:flex;align-items:center;gap:7px}
.pill-dur{font-variant-numeric:tabular-nums;color:var(--text-dim);font-weight:600;font-size:11px}
.pill-dur + span::before{content:"·";margin-right:7px;color:rgba(255,255,255,.25)}
.item-actions{display:flex;align-items:center;gap:5px;flex-shrink:0;opacity:.85;transition:opacity .18s}
.item:hover .item-actions{opacity:1}
.item-actions button{padding:7px 11px;font-size:11.5px;border-radius:99px}

/* Skeleton di caricamento */
.skeleton{display:flex;align-items:center;gap:13px;padding:7px 8px;flex-shrink:0}
.skeleton i{display:block;border-radius:8px;background:linear-gradient(90deg,rgba(255,255,255,.04),rgba(255,255,255,.09),rgba(255,255,255,.04));background-size:200% 100%;animation:shimmer 1.3s infinite linear}
.skeleton .s-thumb{width:50px;height:50px;border-radius:10px;flex-shrink:0}
.skeleton .s-lines{flex:1;display:flex;flex-direction:column;gap:7px}
.skeleton .s-l1{height:11px;width:55%}
.skeleton .s-l2{height:9px;width:35%}
@keyframes shimmer{from{background-position:200% 0}to{background-position:-200% 0}}

.empty-state{
  margin:auto;padding:30px 18px;text-align:center;
  display:flex;flex-direction:column;align-items:center;gap:9px;color:var(--text-dim);max-width:380px;
}
.empty-icon{
  width:60px;height:60px;border-radius:20px;margin-bottom:4px;
  background:linear-gradient(145deg,rgba(229,160,13,.16),rgba(88,101,242,.14));
  border:1px solid var(--border-hi);
  display:flex;align-items:center;justify-content:center;color:var(--accent-hi);
  box-shadow:0 14px 30px -10px rgba(229,160,13,.35);
}
.empty-icon svg{width:26px;height:26px}
.empty-title{font-size:15px;font-weight:700;color:var(--text);letter-spacing:-.2px}
.empty-sub{font-size:12.5px;line-height:1.55;color:var(--text-dim)}

/* Account & Config */
.cfg-grid{flex:1;display:flex;flex-direction:column;gap:12px;overflow-y:auto;min-height:0;margin:0 -6px;padding:0 6px 4px}
.cfg-box{
  background:rgba(255,255,255,.028);border:1px solid var(--border);
  border-radius:var(--radius-lg);padding:16px;
  display:flex;flex-direction:column;gap:12px;flex-shrink:0;
}
.cfg-title{font-size:13.5px;font-weight:700;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;letter-spacing:-.15px}
.cfg-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.cfg-row label{font-size:12px;color:var(--text-dim);min-width:140px;font-weight:600}
.cfg-row input,.cfg-row select{flex:1;min-width:120px}
.hint{font-size:12px;line-height:1.6;color:var(--text-dim);white-space:normal}
.pin-card{
  display:none;flex-direction:column;gap:12px;padding:18px;text-align:center;
  background:linear-gradient(180deg,rgba(229,160,13,.08),rgba(0,0,0,.25));
  border:1px solid rgba(229,160,13,.35);border-radius:var(--radius-md);
}
.pin-code{
  font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
  font-size:32px;font-weight:800;letter-spacing:10px;color:var(--accent-hi);
  padding:8px 10px 8px 20px;margin:0 auto;display:inline-block;
  text-shadow:0 0 24px rgba(229,160,13,.4);user-select:all;cursor:pointer;
}
.lib-item{
  display:flex;align-items:center;justify-content:space-between;gap:8px;
  padding:9px 12px;background:rgba(0,0,0,.22);border:1px solid var(--border);
  border-radius:var(--radius-sm);font-size:12.5px;
}

.toast{
  position:fixed;bottom:calc(22px + var(--safe-bottom));left:50%;
  transform:translate(-50%,20px);opacity:0;pointer-events:none;
  background:rgba(24,26,34,.92);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid var(--border-hi);
  padding:11px 18px;border-radius:99px;font-size:12.5px;font-weight:600;
  display:block;z-index:100;box-shadow:0 18px 40px rgba(0,0,0,.6);
  max-width:calc(100vw - 32px);text-align:center;
  transition:opacity .25s var(--ease),transform .25s var(--ease);
}
.toast.show{opacity:1;transform:translate(-50%,0)}

::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:99px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.2)}

@media (prefers-reduced-motion: reduce){*{animation:none !important;transition:none !important}}

/* ==========================================================================
   MODALITÀ RIDOTTA (Discord Activity Docked / Picture-in-Picture)
   Mostra ESCLUSIVAMENTE cover, titolo e autore del brano, senza barre o menu.
   ========================================================================== */
@media (max-height: 235px), (max-width: 380px) and (max-height: 280px) {
  header{display:none !important}
  .tabs{display:none !important}
  #main-panel{display:none !important}
  .toast{display:none !important}
  html,body{height:100% !important;overflow:hidden !important}
  main{display:flex !important;flex-direction:column !important;padding:0 !important;margin:0 !important;width:100% !important;height:100% !important}
  #player-panel{
    position:fixed !important;inset:0 !important;width:100% !important;height:100% !important;
    margin:0 !important;padding:10px 14px !important;border-radius:0 !important;border:none !important;
    background:transparent !important;backdrop-filter:none !important;-webkit-backdrop-filter:none !important;
    box-shadow:none !important;display:flex !important;flex-direction:row !important;align-items:center !important;
    justify-content:space-between !important;gap:12px !important;z-index:50 !important;
  }
  .player-sheet-bar,.vol-row,.listeners-pill,#btn-restart,#btn-skip,#btn-shuffle,#btn-stop,#btn-leave,#btn-expand-player{display:none !important}
  .now-row{flex-direction:row !important;text-align:left !important;align-items:center !important;gap:12px !important;flex:1 !important;min-width:0 !important;height:100% !important;cursor:pointer}
  .art-wrap{
    width:clamp(66px,36vw,84px) !important;height:clamp(66px,36vw,84px) !important;max-width:84px !important;
    border-radius:14px !important;flex-shrink:0 !important;transform:none !important;box-shadow:0 8px 24px rgba(0,0,0,.65) !important;
  }
  .art-wrap svg{width:32px !important;height:32px !important}
  .eq-overlay{display:none !important}
  .now-meta{flex:1 !important;min-width:0 !important;display:flex !important;flex-direction:column !important;gap:3px !important;justify-content:center !important}
  .now-title{font-size:clamp(14px,4.2vw,17px) !important;font-weight:800 !important;letter-spacing:-.2px !important;white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important;color:#fff !important}
  #now-artist{font-size:clamp(12px,3.4vw,14px) !important;font-weight:600 !important;color:var(--accent-hi) !important;white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important}
  #now-album{display:none !important}
  .controls{display:flex !important;align-items:center !important;flex-shrink:0 !important}
  #btn-play{width:clamp(40px,12vw,48px) !important;height:clamp(40px,12vw,48px) !important;border-radius:50% !important;box-shadow:0 4px 16px rgba(229,160,13,.5) !important;flex-shrink:0 !important}
  #btn-play svg{width:22px !important;height:22px !important}
  .progress-box{position:absolute !important;left:0 !important;right:0 !important;bottom:0 !important;height:3px !important;padding:0 !important;gap:0 !important;pointer-events:none !important}
  .progress-box .bar{height:3px !important;border-radius:0 !important;background:rgba(255,255,255,.08) !important}
  .progress-box .bar-fill{border-radius:0 !important;box-shadow:none !important}
  .progress-box .bar-fill::after,.progress-box .times{display:none !important}
}

body.is-reduced header{display:none !important}
body.is-reduced .tabs{display:none !important}
body.is-reduced #main-panel{display:none !important}
body.is-reduced .toast{display:none !important}
body.is-reduced{height:100% !important;overflow:hidden !important}
body.is-reduced main{display:flex !important;flex-direction:column !important;padding:0 !important;margin:0 !important;width:100% !important;height:100% !important}
body.is-reduced #player-panel{
  position:fixed !important;inset:0 !important;width:100% !important;height:100% !important;
  margin:0 !important;padding:10px 14px !important;border-radius:0 !important;border:none !important;
  background:transparent !important;backdrop-filter:none !important;-webkit-backdrop-filter:none !important;
  box-shadow:none !important;display:flex !important;flex-direction:row !important;align-items:center !important;
  justify-content:space-between !important;gap:12px !important;z-index:50 !important;
}
body.is-reduced .player-sheet-bar,
body.is-reduced .vol-row,
body.is-reduced .listeners-pill,
body.is-reduced #btn-restart,
body.is-reduced #btn-skip,
body.is-reduced #btn-shuffle,
body.is-reduced #btn-stop,
body.is-reduced #btn-leave,
body.is-reduced #btn-expand-player{display:none !important}
body.is-reduced .now-row{flex-direction:row !important;text-align:left !important;align-items:center !important;gap:12px !important;flex:1 !important;min-width:0 !important;height:100% !important;cursor:pointer}
body.is-reduced .art-wrap{
  width:clamp(66px,36vw,84px) !important;height:clamp(66px,36vw,84px) !important;max-width:84px !important;
  border-radius:14px !important;flex-shrink:0 !important;transform:none !important;box-shadow:0 8px 24px rgba(0,0,0,.65) !important;
}
body.is-reduced .art-wrap svg{width:32px !important;height:32px !important}
body.is-reduced .eq-overlay{display:none !important}
body.is-reduced .now-meta{flex:1 !important;min-width:0 !important;display:flex !important;flex-direction:column !important;gap:3px !important;justify-content:center !important}
body.is-reduced .now-title{font-size:clamp(14px,4.2vw,17px) !important;font-weight:800 !important;letter-spacing:-.2px !important;white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important;color:#fff !important}
body.is-reduced #now-artist{font-size:clamp(12px,3.4vw,14px) !important;font-weight:600 !important;color:var(--accent-hi) !important;white-space:nowrap !important;overflow:hidden !important;text-overflow:ellipsis !important}
body.is-reduced #now-album{display:none !important}
body.is-reduced .controls{display:flex !important;align-items:center !important;flex-shrink:0 !important}
body.is-reduced #btn-play{width:clamp(40px,12vw,48px) !important;height:clamp(40px,12vw,48px) !important;border-radius:50% !important;box-shadow:0 4px 16px rgba(229,160,13,.5) !important;flex-shrink:0 !important}
body.is-reduced #btn-play svg{width:22px !important;height:22px !important}
body.is-reduced .progress-box{position:absolute !important;left:0 !important;right:0 !important;bottom:0 !important;height:3px !important;padding:0 !important;gap:0 !important;pointer-events:none !important}
body.is-reduced .progress-box .bar{height:3px !important;border-radius:0 !important;background:rgba(255,255,255,.08) !important}
body.is-reduced .progress-box .bar-fill{border-radius:0 !important;box-shadow:none !important}
body.is-reduced .progress-box .bar-fill::after,
body.is-reduced .progress-box .times{display:none !important}

/* ==========================================================================
   INTERFACCIA MOBILE & COMPACT SPLIT-VIEW (Smartphone, Tablet, Chat Vocale)
   ========================================================================== */
@media (max-width: 820px), (max-height: 540px) {
  header{padding:calc(8px + var(--safe-top)) 12px 8px;gap:8px;max-width:100vw;overflow:hidden}
  .header-meta,#sdk-status,#mode-badge,#srv{display:none !important}
  .brand-title{font-size:15px}
  .logo-mark{width:28px;height:28px;border-radius:9px}
  .logo-mark svg{width:15px;height:15px}
  .header-right{gap:6px;flex-shrink:0}
  .badge{max-width:120px;font-size:10.5px;padding:4px 8px}
  #btn-header-rpc{max-width:115px;padding:4px 8px;font-size:10.5px}
  #sync-badge{max-width:115px;padding:4px 8px;font-size:10.5px}

  main{display:flex;flex-direction:column;padding:0;gap:0;flex:1;min-height:0;overflow:hidden}

  #main-panel{
    order:1;flex:1;min-height:0;overflow:hidden;border-radius:0;border:none;background:transparent;
    backdrop-filter:none;-webkit-backdrop-filter:none;box-shadow:none;
    padding:4px 10px 0;display:flex;flex-direction:column;gap:0;
  }

  .tabs{
    position:fixed;left:0;right:0;bottom:0;z-index:35;
    border-radius:0;border:none;border-top:1px solid var(--border);
    background:rgba(12,13,18,.92);
    backdrop-filter:blur(26px) saturate(1.4);-webkit-backdrop-filter:blur(26px) saturate(1.4);
    padding:5px 4px calc(5px + var(--safe-bottom));gap:2px;justify-content:space-around;
  }
  .tab{flex-direction:column;padding:6px 4px;font-size:10px;gap:3px;border-radius:10px;border:none}
  .tab svg{width:21px;height:21px}
  .tab.active{background:transparent;box-shadow:none;color:#fff}
  .tab-count{position:absolute;margin:-6px 0 0 18px;padding:0 5px;font-size:9px;background:var(--accent);color:var(--accent-ink)}
  .tab{position:relative}

  body:not(.player-expanded):not(.is-reduced) #player-panel{
    order:2;flex-shrink:0;
    margin:4px 8px calc(60px + var(--safe-bottom));
    padding:7px 10px;border-radius:14px;
    background:rgba(30,32,42,.92);border:1px solid var(--border-hi);
    box-shadow:0 10px 24px rgba(0,0,0,.5);
    flex-direction:row;align-items:center;gap:9px;
  }
  body:not(.player-expanded):not(.is-reduced) .now-row{flex-direction:row;text-align:left;gap:11px;flex:1;min-width:0;cursor:pointer}
  body:not(.player-expanded):not(.is-reduced) .art-wrap{width:44px;height:44px;max-width:44px;border-radius:9px;transform:none !important}
  body:not(.player-expanded):not(.is-reduced) .art-wrap svg{width:22px;height:22px}
  body:not(.player-expanded):not(.is-reduced) .eq-overlay{display:none !important}
  body:not(.player-expanded):not(.is-reduced) .now-title{font-size:13.5px}
  body:not(.player-expanded):not(.is-reduced) #now-artist{font-size:11.5px}
  body:not(.player-expanded):not(.is-reduced) #now-album{display:none}
  body:not(.player-expanded):not(.is-reduced) .progress-box{position:absolute;left:14px;right:14px;bottom:0;padding:0;gap:0;pointer-events:none}
  body:not(.player-expanded):not(.is-reduced) .bar{height:2px;background:rgba(255,255,255,.08)}
  body:not(.player-expanded):not(.is-reduced) .bar-fill{box-shadow:none}
  body:not(.player-expanded):not(.is-reduced) .bar-fill::after,
  body:not(.player-expanded):not(.is-reduced) .times,
  body:not(.player-expanded):not(.is-reduced) .vol-row,
  body:not(.player-expanded):not(.is-reduced) .listeners-pill,
  body:not(.player-expanded):not(.is-reduced) .ctrl-extra{display:none !important}
  body:not(.player-expanded):not(.is-reduced) .controls{gap:2px;flex-wrap:nowrap}
  body:not(.player-expanded):not(.is-reduced) #btn-play{width:40px;height:40px;box-shadow:none}
  body:not(.player-expanded):not(.is-reduced) #btn-play svg{width:20px;height:20px}
  body:not(.player-expanded):not(.is-reduced) #btn-skip{width:36px;height:36px}
  body:not(.player-expanded):not(.is-reduced) #btn-expand-player{display:inline-flex;width:34px;height:34px}

  body.player-expanded #player-panel{
    position:fixed;inset:0;z-index:45;border-radius:0;border:none;
    background:linear-gradient(180deg,rgba(30,30,38,.96),rgba(8,9,12,.98));
    backdrop-filter:blur(40px);-webkit-backdrop-filter:blur(40px);
    padding:calc(14px + var(--safe-top)) 24px calc(26px + var(--safe-bottom));
    justify-content:space-evenly;animation:sheetin .35s var(--ease);
  }
  @keyframes sheetin{from{transform:translateY(40px);opacity:0}to{transform:none;opacity:1}}
  body.player-expanded .player-sheet-bar{display:flex}
  body.player-expanded .art-wrap{max-width:min(74vw,300px);border-radius:22px}
  body.player-expanded .now-title{font-size:20px}
  body.player-expanded #btn-play{width:68px;height:68px}

  .cfg-grid, .list{
    flex:1;min-height:0;overflow-y:auto;
    -webkit-overflow-scrolling:touch;touch-action:pan-y;overscroll-behavior-y:contain;
    padding-bottom:30px !important;margin:0 !important;
  }

  .item{padding:6px;gap:11px}
  .item-thumb{width:46px;height:46px;min-width:46px}
  .item-actions button{padding:6px 10px;font-size:11px}
  .cfg-inline-group{display:flex;gap:6px;width:100%}
  .cfg-inline-group input,.cfg-inline-group select{flex:1;min-width:0}
  .cfg-inline-group button{flex-shrink:0;padding:0 12px}
  .cfg-row.cfg-row-buttons{display:flex !important;flex-direction:row !important;gap:8px !important}
  .cfg-row.cfg-row-buttons button{flex:1 !important;width:auto !important}
  .toast{bottom:calc(136px + var(--safe-bottom))}
}

@media (max-width: 540px) {
  .cfg-box{padding:13px;gap:10px;border-radius:14px}
  .cfg-title{font-size:13px}
  .cfg-row:not(.cfg-row-buttons):not(.cfg-row-check){display:flex;flex-direction:column;align-items:stretch;gap:6px}
  .cfg-row label{width:100%;min-width:0;font-size:11.5px;margin-bottom:1px}
  .cfg-row input,.cfg-row select{width:100%;min-width:0;box-sizing:border-box}
  .cfg-row > button{width:100%;height:38px;font-size:12.5px}
  .search-bar{display:flex;flex-direction:column;gap:6px}
  .search-bar select,.search-bar button{width:100%;height:38px}
  #pl-header-bar{flex-direction:column;gap:6px}
  #pl-header-bar button{width:100%;height:38px}
  #pl-detail-bar{flex-direction:column;align-items:stretch;gap:8px}
  #pl-detail-bar > div:last-child{display:flex;gap:6px;width:100%}
  #pl-detail-bar > div:last-child button{flex:1}
  .lib-item span{font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;flex:1}
  .lib-item button{padding:5px 9px;font-size:11px}
}

@media (max-width: 440px) {
  .item-actions .lbl-hide-xs{display:none}
  .item-actions button{width:34px;height:34px;padding:0}
}
</style>
</head>
<body>
<div id="ambient-bg"></div>
<div id="ambient-grad"></div>

<header>
  <div class="brand">
    <span class="logo-mark">
      <img src="/api/logo" alt="Plexcord" onerror="this.style.display='none';this.nextElementSibling.style.display='block'" style="width:100%;height:100%;object-fit:cover;border-radius:inherit">
      <svg style="display:none" viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
    </span>
    <span class="brand-title">Plexcord</span>
    <div class="header-meta">
      <span class="badge" id="srv" data-i18n="srv_connecting">Connecting...</span>
      <span class="badge mode-act" id="mode-badge" data-i18n="mode_activity">Activity</span>
    </div>
  </div>
  <div class="header-right">
    <button type="button" class="badge rpc-btn" id="btn-header-rpc" title="Discord Rich Presence" data-i18n-title="rpc_header_title"><span class="dot"></span><span data-i18n="rpc_btn_enable">Enable RPC</span></button>
    <span class="badge sync-ok" id="sync-badge" style="display:none" data-i18n="sync_plex">🎧 Sync Plex</span>
    <span class="badge" id="sdk-status" data-i18n="sdk_status">Web / Activity</span>
  </div>
</header>

<main>
  <section class="panel" id="player-panel">
    <div class="player-sheet-bar">
      <button type="button" class="icon-btn" id="btn-collapse-player" title="Collapse player" data-i18n-title="btn_collapse_player">
        <svg viewBox="0 0 24 24"><path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41Z"/></svg>
      </button>
      <span class="sheet-title" data-i18n="sheet_now_playing">Now Playing</span>
      <span style="width:38px"></span>
    </div>

    <div class="now-row" id="now-row-tap">
      <div class="art-wrap" id="art">
        <span id="art-icon">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </span>
        <div class="eq-overlay" id="eq-overlay"><div class="eq-bar"></div><div class="eq-bar"></div><div class="eq-bar"></div></div>
      </div>
      <div class="now-meta">
        <div class="now-title" id="now-title" data-i18n="now_empty_title">Nothing playing</div>
        <div class="now-sub" id="now-artist" data-i18n="now_empty_sub">Search for a track to begin</div>
        <div class="now-sub" id="now-album"></div>
      </div>
    </div>

    <div class="progress-box">
      <div class="bar" id="seek-bar" title="Click to seek" data-i18n-title="seek_bar_title"><div class="bar-fill" id="bar-fill"></div></div>
      <div class="times"><span id="t-cur">0:00</span><span id="t-dur">0:00</span></div>
    </div>

    <div class="controls">
      <button type="button" class="icon-btn ctrl-extra" id="btn-restart" title="Restart track" data-i18n-title="btn_restart">
        <svg viewBox="0 0 24 24"><path d="M6 6h2v12H6zm3.5 6 8.5 6V6z"/></svg>
      </button>
      <button type="button" class="primary" id="btn-play" title="Play / Pause" data-i18n-title="btn_play_title">
        <svg viewBox="0 0 24 24" id="ico-play"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        <span class="btn-play-lbl" id="lbl-play" data-i18n="lbl_pause">Pause</span>
      </button>
      <button type="button" class="icon-btn" id="btn-skip" title="Skip track" data-i18n-title="btn_skip">
        <svg viewBox="0 0 24 24"><path d="m6 18 8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
      </button>
      <button type="button" class="icon-btn ctrl-extra" id="btn-shuffle" title="Shuffle queue" data-i18n-title="btn_shuffle">
        <svg viewBox="0 0 24 24"><path d="M10.59 9.17 5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z"/></svg>
      </button>
      <button type="button" class="icon-btn danger ctrl-extra" id="btn-stop" title="Stop & clear queue" data-i18n-title="btn_stop">
        <svg viewBox="0 0 24 24"><path d="M6 6h12v12H6z"/></svg>
      </button>
      <button type="button" class="icon-btn ctrl-extra" id="btn-leave" title="Disconnect from voice" data-i18n-title="btn_leave">
        <svg viewBox="0 0 24 24"><path d="M10.09 15.59 11.5 17l5-5-5-5-1.41 1.41L12.67 11H3v2h9.67l-2.58 2.59zM19 3H5a2 2 0 0 0-2 2v4h2V5h14v14H5v-4H3v4a2 2 0 0 0 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z"/></svg>
      </button>
      <button type="button" class="icon-btn" id="btn-expand-player" title="Expand player" data-i18n-title="btn_expand_player">
        <svg viewBox="0 0 24 24"><path d="M7.41 15.41 12 10.83l4.59 4.58L18 14l-6-6-6 6 1.41 1.41Z"/></svg>
      </button>
    </div>

    <div class="vol-row">
      <button type="button" class="vol-btn" id="btn-voldown" title="Volume -10%">−</button>
      <svg viewBox="0 0 24 24" style="width:15px;height:15px;opacity:.7"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>
      <input type="range" id="vol" min="0" max="150" value="100">
      <button type="button" class="vol-btn" id="btn-volup" title="Volume +10%">+</button>
      <span id="vol-val">100%</span>
    </div>

    <div class="listeners-pill" id="listeners-pill" style="display:none"></div>
  </section>

  <section class="panel" id="main-panel">
    <nav class="tabs" id="main-tabs">
      <button type="button" class="tab active" id="tab-s">
        <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        <span data-i18n="tab_search">Search</span>
      </button>
      <button type="button" class="tab" id="tab-p">
        <svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>
        <span data-i18n="tab_playlists">Playlists</span>
      </button>
      <button type="button" class="tab" id="tab-q">
        <svg viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9h-4v4h-2v-4H9V9h4V5h2v4h4v2z"/></svg>
        <span><span data-i18n="tab_queue">Queue</span> <span class="tab-count" id="q-count">0</span></span>
      </button>
      <button type="button" class="tab" id="tab-u">
        <svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
        <span data-i18n="tab_account">Account</span>
      </button>
      <button type="button" class="tab" id="tab-c">
        <svg viewBox="0 0 24 24"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.48.48 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z"/></svg>
        <span data-i18n="tab_config">Config</span>
      </button>
    </nav>

    <div id="view-s" style="display:flex;flex-direction:column;gap:10px;flex:1;min-height:0">
      <div class="search-bar">
        <div class="search-input-wrap">
          <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
          <input type="search" id="q-in" placeholder="Search track, artist or album on Plex..." data-i18n-ph="search_ph">
        </div>
        <select id="lib-sel"><option value="" data-i18n="search_all_libs">All libraries</option></select>
        <button type="button" class="primary" id="btn-search" data-i18n="btn_search">Search</button>
      </div>
      <div id="s-list" class="list">
        <div class="empty-state">
          <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg></div>
          <div class="empty-title" data-i18n="search_empty_title">Explore your Plex library</div>
          <div class="empty-sub" data-i18n="search_empty_sub">Type a track title or artist name to search with cover preview.</div>
        </div>
      </div>
    </div>

    <div id="view-p" style="display:none;flex-direction:column;gap:10px;flex:1;min-height:0">
      <div class="search-bar" id="pl-header-bar">
        <select id="pl-user-sel" style="flex:1"><option value="" data-i18n="pl_sel_user_ph">Select linked Plex account...</option></select>
        <button type="button" class="primary" id="btn-pl-refresh" data-i18n="btn_refresh">Refresh</button>
      </div>
      <div class="search-bar" id="pl-detail-bar" style="display:none;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:8px;min-width:0">
          <button type="button" id="btn-pl-back" data-i18n="btn_back">← Back</button>
          <span class="item-title" id="pl-detail-title" style="font-size:13.5px">Playlist</span>
        </div>
        <div style="display:flex;gap:6px;flex-shrink:0">
          <button type="button" class="ok" id="btn-pl-play-all" data-i18n="pl_btn_play_all">▶ Now</button>
          <button type="button" id="btn-pl-shuffle-all" data-i18n="pl_btn_shuffle_all">🔀 Shuffle</button>
          <button type="button" class="primary" id="btn-pl-queue-all" data-i18n="pl_btn_queue_all">+ Queue</button>
        </div>
      </div>
      <div id="p-list" class="list">
        <div class="empty-state">
          <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg></div>
          <div class="empty-title" data-i18n="pl_empty_title">Your Plex Playlists</div>
          <div class="empty-sub" data-i18n="pl_empty_sub">Link your personal Plex account in the <b>Account</b> tab to browse and play your playlists.</div>
        </div>
      </div>
    </div>

    <div id="view-q" class="list" style="display:none"></div>

    <div id="view-u" class="cfg-grid" style="display:none">
      <div class="cfg-box">
        <div class="cfg-title">
          <span>🟣 <span data-i18n="acc_rpc_title">Discord Rich Presence (Profile Status)</span></span>
          <span class="badge" id="rpc-status-badge" data-i18n="acc_rpc_not_auth">Not authorized</span>
        </div>
        <div class="hint">
          <span data-i18n="acc_rpc_hint">Show track, artist, and elapsed timer as <b>"Listening to Plex"</b> on your Discord profile. Authorized once per user: status updates automatically while in voice, <b>even with Activity closed</b>.</span>
          <span id="secret-hint" data-i18n="acc_secret_hint"><br>1. In <b>Discord Developer Portal → OAuth2</b>, copy the <b>Client Secret</b>, paste it below, and add a Redirect URL (e.g. <code>https://127.0.0.1</code>).</span>
        </div>
        <div class="cfg-row" id="secret-row">
          <label data-i18n="acc_secret_label">Discord Client Secret</label>
          <input type="password" id="cfg-discord-secret" placeholder="Paste Client Secret from OAuth2..." data-i18n-ph="acc_secret_ph">
          <button type="button" id="btn-save-secret" data-i18n="btn_save_secret">Save Secret</button>
        </div>
        <div class="cfg-row">
          <button type="button" class="blurple" id="btn-auth-rpc" data-i18n="btn_auth_rpc">Authorize Rich Presence</button>
          <button type="button" class="danger" id="btn-revoke-rpc" style="display:none" data-i18n="btn_revoke_rpc">Disable</button>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🎧 <span data-i18n="acc_plex_title">Personal Plex Account (Playlists & Scrobbling)</span></span>
        </div>
        <div class="hint" data-i18n="acc_plex_hint">
          Link your personal Plex account to view your <b>playlists</b> and record listening activity on your <b>Plex Dashboard</b>.<br>
          <i>Note: each user authenticates via 4-digit PIN with their <b>own Plex account</b> on plex.tv (or via the <code>/link</code> command on Discord).</i>
        </div>
        <div class="cfg-row">
          <label data-i18n="acc_your_discord_user">Your Discord user</label>
          <select id="user-sel"><option value="" data-i18n="acc_sel_voice_user">Select your user in the voice channel...</option></select>
        </div>
        <div class="cfg-row cfg-row-buttons">
          <button type="button" class="primary" id="btn-user-pin" data-i18n="btn_user_pin">🔑 Link with 4-Digit PIN</button>
          <button type="button" class="danger" id="btn-user-unlink" data-i18n="btn_user_unlink">Unlink Account</button>
        </div>
        <div class="pin-card" id="user-pin-box">
          <div style="font-size:12px" data-i18n="pin_goto_link">Go to <b>https://plex.tv/link</b> and enter this 4-character code:</div>
          <div class="pin-code" id="user-pin-code" title="Click to copy">----</div>
          <div class="cfg-row cfg-row-buttons" style="justify-content:center">
            <button type="button" class="primary" id="btn-user-open-link" data-i18n="btn_open_link">Open plex.tv/link</button>
            <button type="button" id="btn-user-copy" data-i18n="btn_copy_code">Copy Code</button>
            <button type="button" class="ok" id="btn-user-check" data-i18n="btn_pin_entered">I entered the PIN</button>
          </div>
          <div class="now-sub" data-i18n="pin_auto_poll">⏳ Checking automatically every 3 seconds...</div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title"><span>👥 <span data-i18n="acc_listeners_title">Listeners in Voice Channel</span></span></div>
        <div id="voice-users-list" style="display:flex;flex-direction:column;gap:6px">
          <div class="now-sub" data-i18n="acc_listeners_none">Join a voice channel to link your account.</div>
        </div>
      </div>
    </div>

    <div id="view-c" class="cfg-grid" style="display:none">
      <div class="cfg-box">
        <div class="cfg-title">
          <span>🌐 <span data-i18n="cfg_lang_title">Language / Lingua</span></span>
          <span class="badge" id="cfg-lang-badge">EN</span>
        </div>
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px" data-i18n="cfg_lang_desc">
          Choose the display language for the Web Player and bot slash commands.
        </div>
        <div class="cfg-row">
          <div class="cfg-inline-group">
            <select id="cfg-lang-sel">
              <option value="en">English (Default)</option>
              <option value="it">Italiano</option>
            </select>
            <button type="button" class="primary" id="btn-save-lang" data-i18n="btn_save_lang">Save Language</button>
          </div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🎛️ <span data-i18n="cfg_mode_title">Bot Operating Mode</span></span>
          <span class="badge" id="cfg-mode-label" data-i18n="mode_commands">Commands</span>
        </div>
        <div class="cfg-row cfg-row-buttons">
          <button type="button" class="primary" id="btn-mode-activity" data-i18n="cfg_mode_activity">🎛️ Activity Mode</button>
          <button type="button" id="btn-mode-commands" data-i18n="cfg_mode_commands">💬 Slash Commands Mode</button>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🔑 <span data-i18n="cfg_srv_title">Bot Plex Server (Admin)</span></span>
          <span class="badge" id="cfg-plex-status" data-i18n="cfg_srv_status_check">Checking...</span>
        </div>
        <div class="cfg-row cfg-row-buttons">
          <button type="button" class="primary" id="btn-plex-login" data-i18n="btn_plex_login">🔑 Connect Server with PIN</button>
          <button type="button" class="danger" id="btn-plex-logout" data-i18n="btn_plex_logout">Disconnect Server</button>
        </div>
        <div class="pin-card" id="plex-pin-box">
          <div style="font-size:12px" data-i18n="pin_goto_link">Go to <b>https://plex.tv/link</b> and enter this 4-character code:</div>
          <div class="pin-code" id="plex-pin-code" title="Click to copy">----</div>
          <div class="cfg-row cfg-row-buttons" style="justify-content:center">
            <button type="button" class="primary" id="btn-plex-open-link" data-i18n="btn_open_link">Open plex.tv/link</button>
            <button type="button" id="btn-plex-copy" data-i18n="btn_copy_code">Copy Code</button>
            <button type="button" class="ok" id="btn-plex-complete" data-i18n="btn_pin_entered">I entered the PIN</button>
          </div>
          <div class="now-sub" data-i18n="pin_auto_poll">⏳ Checking automatically every 3 seconds...</div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🖥️ <span data-i18n="cfg_addr_title">Server Selection & Address</span></span>
          <button type="button" id="btn-load-servers" style="padding:5px 10px;font-size:11px" data-i18n="btn_load_servers">Load Servers</button>
        </div>
        <div class="cfg-row">
          <label data-i18n="cfg_addr_manual_lbl">Manual address</label>
          <div class="cfg-inline-group">
            <input type="text" id="cfg-addr" placeholder="Automatic (e.g. http://192.168.1.20:32400)" data-i18n-ph="cfg_addr_ph">
            <button type="button" id="btn-save-addr" data-i18n="btn_save_addr">Save URL</button>
          </div>
        </div>
        <div class="cfg-row">
          <label data-i18n="cfg_srv_lbl">Plex Server</label>
          <div class="cfg-inline-group">
            <select id="cfg-server-sel"><option value="" data-i18n="cfg_srv_click_load">Click 'Load Servers'...</option></select>
            <button type="button" class="primary" id="btn-select-server" data-i18n="btn_select_server">Connect</button>
          </div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>📚 <span data-i18n="cfg_libs_title">Music Libraries</span></span>
          <button type="button" id="btn-libs-all" style="padding:5px 10px;font-size:11px" data-i18n="btn_libs_all">Enable All</button>
        </div>
        <div id="cfg-libs-list" style="display:flex;flex-direction:column;gap:5px">
          <div class="now-sub" data-i18n="cfg_libs_none">Connect a Plex server to view music libraries.</div>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title">
          <span>🛡️ <span data-i18n="cfg_perms_title">Playback Permissions</span></span>
          <span class="badge sync-ok" id="cfg-perm-badge" data-i18n="cfg_perms_badge_all">Everyone</span>
        </div>
        <div style="font-size:12px;color:var(--text-dim);margin-bottom:8px" data-i18n="cfg_perms_desc">
          Choose whether to allow everyone in voice to control playback or restrict commands to administrators and a DJ role.
        </div>
        <div class="cfg-row cfg-row-check" style="align-items:center">
          <label style="display:flex;align-items:center;gap:10px;cursor:pointer;user-select:none;width:100%">
            <input type="checkbox" id="cfg-dj-only" style="width:18px;height:18px;accent-color:var(--accent);cursor:pointer">
            <span style="font-size:13px;font-weight:600" data-i18n="cfg_perms_check_lbl">Restrict controls to Admins and DJ Role only</span>
          </label>
        </div>
        <div class="cfg-row" id="cfg-dj-role-row">
          <label data-i18n="cfg_perms_role_lbl">Authorized role (optional)</label>
          <select id="cfg-dj-role-sel">
            <option value="" data-i18n="cfg_perms_role_none">No role (Administrators only)</option>
          </select>
        </div>
        <div class="cfg-row">
          <button type="button" class="ok" id="btn-save-perms" data-i18n="btn_save_perms">Save Permissions</button>
        </div>
      </div>

      <div class="cfg-box">
        <div class="cfg-title"><span>🔊 <span data-i18n="cfg_audio_title">Audio & Limits</span></span></div>
        <div class="cfg-row">
          <label data-i18n="cfg_audio_vol_lbl">Default volume (0–150%)</label>
          <input type="number" id="cfg-vol" min="0" max="150" value="100">
        </div>
        <div class="cfg-row">
          <label data-i18n="cfg_audio_bit_lbl">Opus bitrate (kbps)</label>
          <input type="number" id="cfg-bit" min="32" max="320" value="128">
        </div>
        <div class="cfg-row">
          <label data-i18n="cfg_audio_idle_lbl">Idle timeout (s)</label>
          <input type="number" id="cfg-idle" min="15" max="1800" value="120">
        </div>
        <div class="cfg-row">
          <label data-i18n="cfg_audio_maxq_lbl">Max tracks in queue</label>
          <input type="number" id="cfg-maxq" min="1" max="500" value="100">
        </div>
        <div class="cfg-row">
          <button type="button" class="ok" id="btn-save-settings" data-i18n="btn_save_settings">Save Settings</button>
        </div>
      </div>
    </div>
  </section>
</main>
<div class="toast" id="toast"></div>
<script>
const params = new URLSearchParams(location.search);
const I18N = {
  en: {
    srv_connecting: "Connecting...",
    mode_activity: "Activity",
    mode_commands: "Commands",
    rpc_header_title: "Show what you are listening to on your Discord profile (Rich Presence)",
    rpc_btn_enable: "Enable RPC",
    rpc_btn_active: "Active",
    sync_plex: "🎧 Sync Plex",
    sdk_status: "Web / Activity",
    sdk_status_act: "Discord Activity Active",
    sheet_now_playing: "Now Playing",
    now_empty_title: "Nothing playing",
    now_empty_sub: "Search for a track to begin",
    btn_collapse_player: "Collapse player",
    btn_expand_player: "Expand player",
    seek_bar_title: "Click to jump to this position",
    btn_restart: "Restart track",
    btn_play_title: "Play / Pause",
    lbl_play: "Play",
    lbl_pause: "Pause",
    lbl_resume: "Resume",
    btn_skip: "Skip track",
    btn_shuffle: "Shuffle queue",
    btn_stop: "Stop & clear queue",
    btn_leave: "Disconnect from voice",
    tab_search: "Search",
    tab_playlists: "Playlists",
    tab_queue: "Queue",
    tab_account: "Account",
    tab_config: "Config",
    search_ph: "Search track, artist or album on Plex...",
    search_all_libs: "All libraries",
    btn_search: "Search",
    search_empty_title: "Explore your Plex library",
    search_empty_sub: "Type a track title or artist name to search with cover preview.",
    search_no_results_title: "No results",
    search_no_results_sub: "No tracks found for this search.",
    search_network_err: "⚠️ Network error while searching.",
    btn_now: "Now",
    btn_queue: "Queue",
    pl_sel_user_ph: "Select linked Plex account...",
    pl_no_users_in_vc: "No linked Plex account in voice channel",
    btn_refresh: "Refresh",
    btn_back: "← Back",
    pl_btn_play_all: "▶ Now",
    pl_btn_shuffle_all: "🔀 Shuffle",
    pl_btn_queue_all: "+ Queue",
    pl_empty_title: "Your Plex Playlists",
    pl_empty_sub: "Link your personal Plex account in the <b>Account</b> tab to browse and play your playlists.",
    pl_not_linked_title: "Plex account not linked yet",
    pl_not_linked_sub: "Link your personal Plex account to browse and play playlists.",
    pl_btn_link_plex: "🔑 Link Plex Account",
    pl_tracks_label: "{count} tracks",
    pl_tap_to_open: "Tap to open",
    pl_empty_playlist: "This playlist is empty.",
    queue_empty_title: "The queue is empty",
    queue_empty_sub: "Use the <b>Search</b> or <b>Playlists</b> tab to add your favorite songs!",
    queue_now_playing_badge: "Now Playing",
    queue_btn_remove: "Remove",
    queue_btn_play_now: "Play now",
    queue_btn_top: "Move to top",
    acc_rpc_title: "Discord Rich Presence (Profile Status)",
    acc_rpc_not_auth: "Not authorized",
    acc_rpc_always_active: "🌐 Always active · {name}",
    acc_rpc_active: "✅ Active · {name}",
    acc_rpc_hint: "Show track, artist, and elapsed timer as <b>&quot;Listening to Plex&quot;</b> on your Discord profile. Authorized once per user: status updates automatically while in voice, <b>even with Activity closed</b>.",
    acc_secret_hint: "<br>1. In <b>Discord Developer Portal → OAuth2</b>, copy the <b>Client Secret</b>, paste it below, and add a Redirect URL (e.g. <code>https://127.0.0.1</code>).",
    acc_secret_label: "Discord Client Secret",
    acc_secret_ph: "Paste Client Secret from OAuth2...",
    btn_save_secret: "Save Secret",
    btn_auth_rpc: "Authorize Rich Presence",
    btn_revoke_rpc: "Disable",
    acc_plex_title: "Personal Plex Account (Playlists & Scrobbling)",
    acc_plex_hint: "Link your personal Plex account to view your <b>playlists</b> and record listening activity on your <b>Plex Dashboard</b>.<br><i>Note: each user authenticates via 4-digit PIN with their <b>own Plex account</b> on plex.tv (or via the <code>/link</code> command on Discord).</i>",
    acc_your_discord_user: "Your Discord user",
    acc_sel_voice_user: "Select your user in the voice channel...",
    btn_user_pin: "🔑 Link with 4-Digit PIN",
    btn_user_unlink: "Unlink Account",
    pin_goto_link: "Go to <b>https://plex.tv/link</b> and enter this 4-character code:",
    btn_open_link: "Open plex.tv/link",
    btn_copy_code: "Copy Code",
    btn_pin_entered: "I entered the PIN",
    pin_auto_poll: "⏳ Checking automatically every 3 seconds...",
    acc_listeners_title: "Listeners in Voice Channel",
    acc_listeners_none: "Join a voice channel to link your account.",
    cfg_lang_title: "Language / Lingua",
    cfg_lang_desc: "Choose the display language for the Web Player and bot slash commands.",
    btn_save_lang: "Save Language",
    cfg_mode_title: "Bot Operating Mode",
    cfg_mode_activity: "🎛️ Activity Mode",
    cfg_mode_commands: "💬 Slash Commands Mode",
    cfg_srv_title: "Bot Plex Server (Admin)",
    cfg_srv_status_check: "Checking...",
    btn_plex_login: "🔑 Connect Server with PIN",
    btn_plex_logout: "Disconnect Server",
    cfg_addr_title: "Server Selection & Address",
    btn_load_servers: "Load Servers",
    cfg_addr_manual_lbl: "Manual address",
    cfg_addr_ph: "Automatic (e.g. http://192.168.1.20:32400)",
    btn_save_addr: "Save URL",
    cfg_srv_lbl: "Plex Server",
    cfg_srv_click_load: "Click 'Load Servers'...",
    btn_select_server: "Connect",
    cfg_libs_title: "Music Libraries",
    btn_libs_all: "Enable All",
    cfg_libs_none: "Connect a Plex server to view music libraries.",
    cfg_lib_enabled: "✅ Enabled",
    cfg_lib_disabled: "❌ Disabled",
    cfg_perms_title: "Playback Permissions",
    cfg_perms_badge_all: "Everyone",
    cfg_perms_badge_dj: "Admin & DJ",
    cfg_perms_admin_only: "Admins only",
    cfg_perms_desc: "Choose whether to allow everyone in voice to control playback or restrict commands to administrators and a DJ role.",
    cfg_perms_check_lbl: "Restrict controls to Admins and DJ Role only",
    cfg_perms_role_lbl: "Authorized role (optional)",
    cfg_perms_role_none: "No role (Administrators only)",
    btn_save_perms: "Save Permissions",
    cfg_audio_title: "Audio & Limits",
    cfg_audio_vol_lbl: "Default volume (0–150%)",
    cfg_audio_bit_lbl: "Opus bitrate (kbps)",
    cfg_audio_idle_lbl: "Idle timeout (s)",
    cfg_audio_maxq_lbl: "Max tracks in queue",
    btn_save_settings: "Save Settings",
    toast_code_copied: "📋 Code {code} copied to clipboard!",
    toast_pin_code: "📋 PIN Code: {code}",
    toast_lang_saved: "🌐 Language saved!",
    toast_settings_saved: "💾 Settings saved.",
    toast_secret_saved: "💾 Discord Client Secret saved! You can now authorize RPC.",
    toast_rpc_revoked: "🗑️ Rich Presence disabled.",
    toast_rpc_active_always: "🟣 Rich Presence enabled! Track remains visible on your profile even with Activity closed.",
    toast_rpc_active_open: "🟣 Rich Presence enabled! Track appears on your profile while Activity is open.",
    toast_rpc_already: "🟣 Rich Presence already active!",
    toast_rpc_enter_secret: "⚠️ Enter Discord Client Secret in Account tab first.",
    toast_rpc_join_voice: "⚠️ Open the Activity directly in Discord voice channel to use RPC.",
    toast_user_linked: "🎧 Plex account '{user}' linked to {name}!",
    toast_user_unlinked: "🗑️ Plex account unlinked from Discord profile.",
    toast_server_connected: "✅ Connected to Plex server: {name}",
    toast_servers_found: "Found {count} Plex servers.",
    toast_login_completed: "✅ Plex login completed! Now select your Plex server.",
    toast_bot_disconnected: "👋 Disconnected from voice channel."
  },
  it: {
    srv_connecting: "Connessione...",
    mode_activity: "Activity",
    mode_commands: "Comandi",
    rpc_header_title: "Mostra il brano in ascolto sul tuo profilo personale Discord (Rich Presence)",
    rpc_btn_enable: "Attiva RPC",
    rpc_btn_active: "Attivo",
    sync_plex: "🎧 Sync Plex",
    sdk_status: "Web / Activity",
    sdk_status_act: "Discord Activity Attiva",
    sheet_now_playing: "In Riproduzione",
    now_empty_title: "Nessun brano in riproduzione",
    now_empty_sub: "Cerca un brano per iniziare",
    btn_collapse_player: "Riduci player",
    btn_expand_player: "Espandi player",
    seek_bar_title: "Clicca per saltare a questo punto",
    btn_restart: "Ricomincia brano",
    btn_play_title: "Play / Pausa",
    lbl_play: "Riproduci",
    lbl_pause: "Pausa",
    lbl_resume: "Riprendi",
    btn_skip: "Salta brano",
    btn_shuffle: "Mescola coda",
    btn_stop: "Ferma e svuota coda",
    btn_leave: "Disconnetti dal canale vocale",
    tab_search: "Cerca",
    tab_playlists: "Playlist",
    tab_queue: "Coda",
    tab_account: "Account",
    tab_config: "Config",
    search_ph: "Cerca brano, artista o album su Plex...",
    search_all_libs: "Tutte le librerie",
    btn_search: "Cerca",
    search_empty_title: "Esplora la tua libreria Plex",
    search_empty_sub: "Digita il titolo di una canzone o il nome di un artista per cercare con anteprima copertina.",
    search_no_results_title: "Nessun risultato",
    search_no_results_sub: "Nessun brano trovato per questa ricerca.",
    search_network_err: "⚠️ Errore di rete durante la ricerca.",
    btn_now: "Ora",
    btn_queue: "Coda",
    pl_sel_user_ph: "Seleziona account Plex collegato...",
    pl_no_users_in_vc: "Nessun account Plex collegato nel canale",
    btn_refresh: "Aggiorna",
    btn_back: "← Indietro",
    pl_btn_play_all: "▶ Ora",
    pl_btn_shuffle_all: "🔀 Shuffle",
    pl_btn_queue_all: "+ Coda",
    pl_empty_title: "Le tue Playlist Plex",
    pl_empty_sub: "Collega il tuo account Plex nella scheda <b>Account</b> per sfogliare e riprodurre le tue playlist personali.",
    pl_not_linked_title: "Account Plex non ancora collegato",
    pl_not_linked_sub: "Collega il tuo account personale Plex per accedere alle tue playlist.",
    pl_btn_link_plex: "🔑 Collega Account Plex",
    pl_tracks_label: "{count} brani",
    pl_tap_to_open: "Tocca per aprire",
    pl_empty_playlist: "Questa playlist è vuota.",
    queue_empty_title: "La coda è vuota",
    queue_empty_sub: "Usa la scheda <b>Cerca</b> o <b>Playlist</b> per aggiungere i tuoi brani preferiti!",
    queue_now_playing_badge: "In riproduzione",
    queue_btn_remove: "Rimuovi",
    queue_btn_play_now: "Riproduci ora",
    queue_btn_top: "Sposta in cima",
    acc_rpc_title: "Discord Rich Presence (Stato Profilo)",
    acc_rpc_not_auth: "Non autorizzato",
    acc_rpc_always_active: "🌐 Sempre attivo · {name}",
    acc_rpc_active: "✅ Attivo · {name}",
    acc_rpc_hint: "Mostra brano, artista e timer come <b>&quot;Sta ascoltando Plex&quot;</b> sul tuo profilo Discord. Ogni ascoltatore autorizza una sola volta: finché è nel canale vocale del bot il suo stato si aggiorna in automatico, <b>anche con l'Activity chiusa</b>.",
    acc_secret_hint: "<br>1. Nel <b>Discord Developer Portal → OAuth2</b> copia il <b>Client Secret</b>, incollalo qui sotto e aggiungi un Redirect URL (es. <code>https://127.0.0.1</code>).",
    acc_secret_label: "Discord Client Secret",
    acc_secret_ph: "Incolla Client Secret da OAuth2...",
    btn_save_secret: "Salva Secret",
    btn_auth_rpc: "Autorizza Rich Presence",
    btn_revoke_rpc: "Disattiva",
    acc_plex_title: "Account Personale Plex (Playlist & Scrobbling)",
    acc_plex_hint: "Collega il tuo account Plex personale per visualizzare le tue <b>playlist</b> e registrare l'attività di ascolto individuale sulla <b>Dashboard di Plex</b>.<br><i>Nota: ogni utente deve autenticare il PIN con il <b>proprio account Plex</b> su plex.tv (o con il comando <code>/link</code> su Discord).</i>",
    acc_your_discord_user: "Il tuo utente Discord",
    acc_sel_voice_user: "Seleziona il tuo utente nel canale vocale...",
    btn_user_pin: "🔑 Collega con PIN a 4 Cifre",
    btn_user_unlink: "Scollega Account",
    pin_goto_link: "Vai su <b>https://plex.tv/link</b> e inserisci questo codice a 4 caratteri:",
    btn_open_link: "Apri plex.tv/link",
    btn_copy_code: "Copia Codice",
    btn_pin_entered: "Ho inserito il PIN",
    pin_auto_poll: "⏳ Verifica automatica ogni 3 secondi...",
    acc_listeners_title: "Ascoltatori nel Canale Vocale",
    acc_listeners_none: "Entra nel canale vocale per collegare il tuo account.",
    cfg_lang_title: "Lingua / Language",
    cfg_lang_desc: "Scegli la lingua dell'interfaccia dell'Activity/Web Player e dei comandi del bot.",
    btn_save_lang: "Salva Lingua",
    cfg_mode_title: "Modalità Operativa Bot",
    cfg_mode_activity: "🎛️ Modalità Activity",
    cfg_mode_commands: "💬 Modalità Comandi Slash",
    cfg_srv_title: "Server Plex del Bot (Admin)",
    cfg_srv_status_check: "Verifica...",
    btn_plex_login: "🔑 Collega Server con PIN",
    btn_plex_logout: "Scollega Server",
    cfg_addr_title: "Scelta Server & Indirizzo",
    btn_load_servers: "Carica Server",
    cfg_addr_manual_lbl: "Indirizzo manuale",
    cfg_addr_ph: "Automatico (es. http://192.168.1.20:32400)",
    btn_save_addr: "Salva URL",
    cfg_srv_lbl: "Server Plex",
    cfg_srv_click_load: "Clicca 'Carica Server'...",
    btn_select_server: "Connetti",
    cfg_libs_title: "Librerie Musicali",
    btn_libs_all: "Abilita Tutte",
    cfg_libs_none: "Collega un server Plex per vedere le librerie musicali.",
    cfg_lib_enabled: "✅ Abilitata",
    cfg_lib_disabled: "❌ Disabilitata",
    cfg_perms_title: "Permessi di Riproduzione",
    cfg_perms_badge_all: "Tutti",
    cfg_perms_badge_dj: "Admin & DJ",
    cfg_perms_admin_only: "Solo Admin",
    cfg_perms_desc: "Scegli se permettere a chiunque nel canale vocale di controllare la musica o riservare i comandi ad amministratori e ruolo DJ.",
    cfg_perms_check_lbl: "Riserva i controlli solo ad Admin e Ruolo DJ",
    cfg_perms_role_lbl: "Ruolo autorizzato (opzionale)",
    cfg_perms_role_none: "Nessun ruolo (solo Amministratori)",
    btn_save_perms: "Salva Permessi",
    cfg_audio_title: "Audio & Limiti",
    cfg_audio_vol_lbl: "Volume predefinito (0–150%)",
    cfg_audio_bit_lbl: "Bitrate Opus (kbps)",
    cfg_audio_idle_lbl: "Timeout inattività (s)",
    cfg_audio_maxq_lbl: "Max brani in coda",
    btn_save_settings: "Salva Impostazioni",
    toast_code_copied: "📋 Codice {code} copiato negli appunti!",
    toast_pin_code: "📋 Codice PIN: {code}",
    toast_lang_saved: "🌐 Lingua salvata!",
    toast_settings_saved: "💾 Impostazioni salvate.",
    toast_secret_saved: "💾 Discord Client Secret salvato! Ora puoi autorizzare l'RPC.",
    toast_rpc_revoked: "🗑️ Rich Presence disattivato.",
    toast_rpc_active_always: "🟣 Rich Presence attivato! Il brano resterà visibile sul tuo profilo anche ad Activity chiusa.",
    toast_rpc_active_open: "🟣 Rich Presence attivato! Il brano appare sul tuo profilo mentre l'Activity è aperta.",
    toast_rpc_already: "🟣 Rich Presence già attivo!",
    toast_rpc_enter_secret: "⚠️ Inserisci prima il Discord Client Secret nella scheda Account.",
    toast_rpc_join_voice: "⚠️ Apri l'Activity direttamente dentro il canale vocale di Discord per usare l'RPC.",
    toast_user_linked: "🎧 Account Plex '{user}' collegato a {name}!",
    toast_user_unlinked: "🗑️ Account Plex scollegato dal profilo Discord.",
    toast_server_connected: "✅ Connesso al server Plex: {name}",
    toast_servers_found: "Trovati {count} server Plex.",
    toast_login_completed: "✅ Login Plex completato! Ora carica e scegli il tuo server Plex.",
    toast_bot_disconnected: "👋 Disconnesso dal canale vocale."
  }
};

let currentLang = localStorage.getItem("plexcord_lang") || "en";
function t(key, vars) {
  const dict = I18N[currentLang] || I18N.en;
  let s = (dict && dict[key]) || (I18N.en && I18N.en[key]) || key;
  if (vars && typeof vars === "object") {
    Object.keys(vars).forEach(k => { s = s.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]); });
  }
  return s;
}
function applyLang(lang) {
  if (!I18N[lang]) lang = "en";
  currentLang = lang;
  try { localStorage.setItem("plexcord_lang", lang); } catch {}
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const k = el.getAttribute("data-i18n");
    if (k) {
      const val = t(k);
      if (val.includes("<")) el.innerHTML = val;
      else el.textContent = val;
    }
  });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => {
    const k = el.getAttribute("data-i18n-ph");
    if (k) el.setAttribute("placeholder", t(k));
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const k = el.getAttribute("data-i18n-title");
    if (k) el.setAttribute("title", t(k));
  });
  const sel = document.getElementById("cfg-lang-sel");
  if (sel && sel.value !== lang) sel.value = lang;
  const badge = document.getElementById("cfg-lang-badge");
  if (badge) badge.textContent = lang.toUpperCase();
}

let guildId = params.get("guild_id") || "";
let channelId = params.get("channel_id") || "";
const token = params.get("token") || "";
const frameId = params.get("frame_id") || "";
const clientId = "__CLIENT_ID__" || params.get("client_id") || "";
let sdkReady = false;
let rpcAuthed = false;
let authInFlight = false;
let stateLoaded = false;
let discordUser = null;
const pendingRpc = new Map();

function getRpcIdentity() {
  try {
    const raw = JSON.parse(localStorage.getItem("plexcord_rpc_identity") || "{}");
    return raw && typeof raw === "object" ? raw : {};
  } catch { return {}; }
}
function setRpcIdentity(patch) {
  try {
    if (patch === null) { localStorage.removeItem("plexcord_rpc_identity"); return; }
    localStorage.setItem("plexcord_rpc_identity", JSON.stringify({...getRpcIdentity(), ...patch}));
  } catch {}
}
try { localStorage.removeItem("plexcord_discord_token"); } catch {}

function rpcCall(cmd, args = {}) {
  if (!frameId || window.parent === window) return Promise.reject(new Error("Non in Discord Activity"));
  const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pendingRpc.delete(nonce);
      reject(new Error("Timeout RPC " + cmd));
    }, 30000);
    pendingRpc.set(nonce, {resolve, reject, timer});
    window.parent.postMessage([1, {cmd, args, nonce}], "*");
  });
}

function openExternalUrl(url) {
  if (!frameId || window.parent === window) {
    window.open(url, "_blank", "noopener");
    return;
  }
  rpcCall("OPEN_EXTERNAL_LINK", {url}).catch(() => window.open(url, "_blank", "noopener"));
}

async function copyText(text) {
  const clean = (text || "").trim();
  if (!clean || clean === "----") return false;
  let ok = false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(clean);
      ok = true;
    }
  } catch {}
  if (!ok) {
    const ta = document.createElement("textarea");
    ta.value = clean;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, clean.length);
    try { ok = document.execCommand("copy"); } catch {}
    document.body.removeChild(ta);
  }
  return ok;
}

function setRpcAuthUI(user) {
  rpcAuthed = true;
  discordUser = user;
  const name = (user && (user.global_name || user.username)) || "Attivo";
  const hdrBtn = document.getElementById("btn-header-rpc");
  hdrBtn.innerHTML = '<span class="dot live"></span>' + esc(name);
  hdrBtn.classList.add("sync-ok");
  document.getElementById("btn-revoke-rpc").style.display = "inline-flex";
  if (user && user.id) {
    const uSel = document.getElementById("user-sel");
    if ([...uSel.options].some(o => o.value === String(user.id))) uSel.value = String(user.id);
  }
  updateRpcBadge();
  lastPresenceKey = "";
  lastPresenceSentAt = 0;
  updateDiscordActivityPresence(true);
}

function serverPresenceActive() {
  return !!(discordUser && (state.presence_live || []).includes(String(discordUser.id)));
}

function updateRpcBadge() {
  const badge = document.getElementById("rpc-status-badge");
  if (!rpcAuthed) {
    badge.textContent = t("acc_rpc_not_auth");
    badge.classList.remove("sync-ok");
    return;
  }
  const name = (discordUser && (discordUser.global_name || discordUser.username)) || t("rpc_btn_active");
  badge.textContent = serverPresenceActive() ? t("acc_rpc_always_active", {name}) : t("acc_rpc_active", {name});
  badge.classList.add("sync-ok");
}

async function tryAuthenticateToken(tok) {
  if (!tok) return false;
  try {
    const auth = await rpcCall("AUTHENTICATE", {access_token: tok});
    setRpcAuthUI(auth && auth.user);
    return true;
  } catch {
    return false;
  }
}

async function tokenApi(body) {
  try {
    const r = await fetch(apiPath("api/discord_token"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({client_id: clientId, ...body})
    });
    const data = await r.json();
    return {ok: r.ok, data};
  } catch {
    return {ok: false, data: {}};
  }
}

async function restoreDiscordRpc() {
  const ident = getRpcIdentity();
  if (!ident.user_id || !ident.key) return false;
  for (const refresh of [false, true]) {
    const res = await tokenApi({action: "restore", user_id: ident.user_id, key: ident.key, refresh});
    if (res.ok && res.data.access_token && await tryAuthenticateToken(res.data.access_token)) return true;
    if (res.ok && !res.data.access_token) break;
  }
  return false;
}

async function authorizeDiscordRpc(interactive = false) {
  if (!sdkReady || !clientId) {
    if (interactive) msg("⚠️ Apri l'Activity direttamente dentro il canale vocale di Discord per usare l'RPC.");
    return;
  }
  if (rpcAuthed) {
    lastPresenceKey = "";
    lastPresenceSentAt = 0;
    updateDiscordActivityPresence(true);
    if (interactive) msg("🟣 Rich Presence attivo sul tuo profilo Discord.");
    return;
  }
  if (authInFlight) return;
  authInFlight = true;
  try {
    // 1. Ripristino silenzioso del token salvato sul server (nessun popup).
    if (await restoreDiscordRpc()) {
      if (interactive) msg("🟣 Rich Presence già attivo!");
      return;
    }
    // Il popup di autorizzazione compare SOLO dopo un click esplicito.
    if (!interactive) return;

    if (!state.has_discord_secret) {
      showTab("u");
      msg("⚠️ Inserisci prima il Discord Client Secret nella scheda Account.");
      document.getElementById("cfg-discord-secret").focus();
      return;
    }

    let authRes = null;
    const base = ["identify", "rpc.activities.write"];
    try {
      // activities.write abilita lo stato "sempre attivo" anche ad Activity chiusa.
      authRes = await rpcCall("AUTHORIZE", {client_id: clientId, response_type: "code", state: "", prompt: "none", scope: [...base, "activities.write"]});
    } catch {
      authRes = await rpcCall("AUTHORIZE", {client_id: clientId, response_type: "code", state: "", prompt: "none", scope: base});
    }
    if (!authRes || !authRes.code) throw new Error("Codice OAuth2 non ricevuto");
    const res = await tokenApi({action: "exchange", code: authRes.code});
    if (!res.ok || !res.data.access_token) throw new Error(res.data.error || "Scambio token Discord fallito");
    setRpcIdentity({user_id: res.data.user_id, key: res.data.key});
    if (!await tryAuthenticateToken(res.data.access_token)) {
      throw new Error("Autenticazione RPC con Discord non riuscita");
    }
    msg(res.data.server_presence
      ? "🟣 Rich Presence attivato! Il brano resterà visibile sul tuo profilo anche ad Activity chiusa."
      : "🟣 Rich Presence attivato! Il brano appare sul tuo profilo mentre l'Activity è aperta.");
  } catch (err) {
    if (interactive) msg("⚠️ " + (err.message || "Autorizzazione Discord RPC non riuscita."));
  } finally {
    authInFlight = false;
  }
}

async function revokeDiscordRpc() {
  const ident = getRpcIdentity();
  if (ident.user_id && ident.key) await tokenApi({action: "revoke", user_id: ident.user_id, key: ident.key});
  if (rpcAuthed) rpcCall("SET_ACTIVITY", {activity: null}).catch(() => {});
  setRpcIdentity(null);
  rpcAuthed = false;
  discordUser = null;
  const hdrBtn = document.getElementById("btn-header-rpc");
  hdrBtn.innerHTML = '<span class="dot"></span>' + t("rpc_btn_enable");
  hdrBtn.classList.remove("sync-ok");
  document.getElementById("btn-revoke-rpc").style.display = "none";
  updateRpcBadge();
  msg(t("toast_rpc_revoked"));
}

function initDiscordSdk() {
  if (!frameId || window.parent === window) return;
  document.getElementById("sdk-status").textContent = "Discord Activity";
  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (!Array.isArray(d) || d[0] !== 1 || !d[1]) return;
    const p = d[1];
    if (p.nonce && pendingRpc.has(p.nonce)) {
      const entry = pendingRpc.get(p.nonce);
      pendingRpc.delete(p.nonce);
      clearTimeout(entry.timer);
      if (p.evt === "ERROR") {
        entry.reject(new Error((p.data && p.data.message) || "Errore RPC"));
      } else {
        entry.resolve(p.data);
      }
      return;
    }
    if (p.cmd === "DISPATCH" && (p.evt === "ACTIVITY_LAYOUT_MODE_UPDATE" || p.evt === "ACTIVITY_PIP_MODE_UPDATE")) {
      const data = p.data || {};
      isSdkPip = (data.layout_mode === 1 || data.layout_mode === "PIP" || data.is_pip === true);
      updateReducedMode();
      return;
    }
    if (p.cmd === "DISPATCH" && p.evt === "READY") {
      sdkReady = true;
      document.getElementById("sdk-status").textContent = t("sdk_status_act");
      rpcCall("SUBSCRIBE", {evt: "ACTIVITY_LAYOUT_MODE_UPDATE"}).catch(() => {});
      rpcCall("SUBSCRIBE", {evt: "ACTIVITY_PIP_MODE_UPDATE"}).catch(() => {});
      setTimeout(() => authorizeDiscordRpc(false), 300);
    }
  });
  window.parent.postMessage([0, {
    v: 1,
    encoding: "json",
    client_id: clientId,
    frame_id: frameId,
    sdk_version: "1.9.0"
  }], "*");
}
initDiscordSdk();

function padRpcStr(s, fallback) {
  let clean = String(s || fallback || "Plexcord").trim();
  if (clean.length < 2) clean = (clean + " · Plex").slice(0, 128);
  return clean.slice(0, 128);
}

let lastPresenceKey = "";
let lastPresenceTrackId = "";
let lastPresencePaused = false;
let lastPresenceStartSec = 0;
let lastPresenceSentAt = 0;
let presenceTimer = null;

let clientPresenceCleared = false;
function updateDiscordActivityPresence(force = false) {
  if (!sdkReady || !rpcAuthed || !stateLoaded) return;
  if (serverPresenceActive()) {
    // Lo stato è già pubblicato dal server per tutti gli ascoltatori autorizzati: evita duplicati.
    if (!clientPresenceCleared) {
      clientPresenceCleared = true;
      rpcCall("SET_ACTIVITY", {activity: null}).catch(() => {});
    }
    return;
  }
  if (clientPresenceCleared) { clientPresenceCleared = false; force = true; }
  const cur = state.current;
  const nowMs = Date.now();
  const nowSec = Math.floor(nowMs / 1000);

  if (!cur) {
    if (lastPresenceKey === "idle" && !force) return;
    lastPresenceKey = "idle";
    lastPresenceTrackId = "";
    const idleAct = {
      type: 2,
      details: padRpcStr("In attesa di un brano", "Plexcord"),
      state: padRpcStr("Plexcord · " + (state.server_name || "Plex"), "Plex")
    };
    rpcCall("SET_ACTIVITY", {activity: idleAct}).catch(() => {
      rpcCall("SET_ACTIVITY", {activity: {...idleAct, type: 0}}).catch(() => {});
    });
    return;
  }

  const durSec = Math.floor((cur.duration || 0) / 1000);
  const elSec = Math.max(0, Math.min(durSec || (state.elapsed || 0), state.elapsed || 0));
  const computedStartSec = nowSec - elSec;
  const trackChanged = cur.id !== lastPresenceTrackId;
  const pauseChanged = Boolean(state.paused) !== lastPresencePaused;
  const seeked = !state.paused && Math.abs(computedStartSec - lastPresenceStartSec) >= 6;

  if (!force && !trackChanged && !pauseChanged && !seeked) return;

  // Rispetta il rate-limit RPC di Discord evitando invii ravvicinati
  const elapsedSinceLast = nowMs - lastPresenceSentAt;
  if (!force && !trackChanged && elapsedSinceLast < 4000) {
    clearTimeout(presenceTimer);
    presenceTimer = setTimeout(() => updateDiscordActivityPresence(true), 4000 - elapsedSinceLast);
    return;
  }

  lastPresenceKey = `${cur.id}:${state.paused}`;
  lastPresenceTrackId = cur.id;
  lastPresencePaused = Boolean(state.paused);
  lastPresenceStartSec = computedStartSec;
  lastPresenceSentAt = nowMs;

  const detailsStr = padRpcStr((state.paused ? "⏸️ " : "🎵 ") + cur.title, "Brano su Plex");
  const stateStr = padRpcStr("di " + cur.artist + (cur.album ? " · " + cur.album : ""), "Artista");
  const actObj = {
    type: 2,
    details: detailsStr,
    state: stateStr
  };
  if (!state.paused && durSec > 0) {
    const startMs = nowMs - (elSec * 1000);
    const endMs = startMs + Math.max(1000, durSec * 1000);
    actObj.timestamps = {
      start: startMs,
      end: endMs
    };
  }
  rpcCall("SET_ACTIVITY", {activity: actObj}).catch(() => {
    rpcCall("SET_ACTIVITY", {activity: {...actObj, type: 0}}).catch(() => {});
  });
}

function fmt(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const m = Math.floor(sec / 60), s = sec % 60;
  return m + ":" + (s < 10 ? "0" : "") + s;
}
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}
function msg(text) {
  const el = document.getElementById("toast");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(window._t);
  window._t = setTimeout(() => el.classList.remove("show"), 3200);
}
function apiPath(path) {
  const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
  return base + path + "?" + new URLSearchParams({guild_id: guildId, channel_id: channelId, token}).toString();
}
function artUrlFor(trackId) {
  return apiPath("api/art/" + encodeURIComponent(guildId || "0") + "/" + encodeURIComponent(trackId));
}

const artOkCache = new Set();
let thumbQueue = [];
let activeThumbLoads = 0;

function mountThumbImage(box, url) {
  const img = new Image();
  img.alt = "";
  img.src = url;
  box.innerHTML = "";
  box.appendChild(img);
}

function pumpThumbQueue() {
  while (activeThumbLoads < 6 && thumbQueue.length > 0) {
    const box = thumbQueue.shift();
    if (!box || !box.isConnected) continue;
    const url = box.getAttribute("data-art");
    if (!url) continue;
    box.removeAttribute("data-art");
    if (artOkCache.has(url)) {
      mountThumbImage(box, url);
      continue;
    }
    activeThumbLoads++;
    const img = new Image();
    img.alt = "";
    img.onload = () => {
      activeThumbLoads--;
      artOkCache.add(url);
      if (box.isConnected) {
        box.innerHTML = "";
        box.appendChild(img);
      }
      pumpThumbQueue();
    };
    img.onerror = () => {
      activeThumbLoads--;
      pumpThumbQueue();
    };
    img.src = url;
  }
}

function hydrateThumbs(root) {
  if (!root) return;
  root.querySelectorAll(".item-thumb[data-art]").forEach(box => {
    const url = box.getAttribute("data-art");
    if (!url) return;
    if (artOkCache.has(url)) {
      box.removeAttribute("data-art");
      mountThumbImage(box, url);
    } else {
      thumbQueue.push(box);
    }
  });
  pumpThumbQueue();
}

let isSdkPip = false;
function isReducedMode() {
  return isSdkPip || window.innerHeight <= 235 || (window.innerWidth <= 380 && window.innerHeight <= 280);
}
function updateReducedMode() {
  const red = isReducedMode();
  document.body.classList.toggle("is-reduced", red);
  if (red) {
    document.body.classList.remove("player-expanded");
  }
}
window.addEventListener("resize", updateReducedMode);

function isMobileView() {
  return window.matchMedia("(max-width: 820px), (max-height: 540px)").matches;
}

function showTab(t) {
  document.body.classList.remove("player-expanded");
  ["s", "p", "q", "u", "c"].forEach(k => {
    document.getElementById("tab-" + k).classList.toggle("active", k === t);
    const v = document.getElementById("view-" + k);
    v.style.display = k === t ? "flex" : "none";
    if (k === t) { v.classList.remove("view-anim"); void v.offsetWidth; v.classList.add("view-anim"); }
  });
  if (t === "s" && !isMobileView()) document.getElementById("q-in").focus();
  if (t === "p") loadPlaylists();
}
document.getElementById("tab-s").addEventListener("click", () => showTab("s"));
document.getElementById("tab-p").addEventListener("click", () => showTab("p"));
document.getElementById("tab-q").addEventListener("click", () => showTab("q"));
document.getElementById("tab-u").addEventListener("click", () => showTab("u"));
document.getElementById("tab-c").addEventListener("click", () => showTab("c"));
document.getElementById("btn-header-rpc").addEventListener("click", () => authorizeDiscordRpc(true));
document.getElementById("btn-auth-rpc").addEventListener("click", () => authorizeDiscordRpc(true));
document.getElementById("btn-revoke-rpc").addEventListener("click", revokeDiscordRpc);

function skeletonRows(n = 6) {
  return Array.from({length: n}, () => '<div class="skeleton"><i class="s-thumb"></i><div class="s-lines"><i class="s-l1"></i><i class="s-l2"></i></div></div>').join("");
}
function setVolFill(el) {
  const max = Number(el.max || 100);
  el.style.setProperty("--fill", (Number(el.value) / max * 100) + "%");
}

document.getElementById("btn-expand-player").addEventListener("click", () => {
  document.body.classList.add("player-expanded");
});
document.getElementById("btn-collapse-player").addEventListener("click", () => {
  document.body.classList.remove("player-expanded");
});
document.getElementById("now-row-tap").addEventListener("click", () => {
  if (isReducedMode()) {
    act("toggle");
    return;
  }
  if (isMobileView() && !document.body.classList.contains("player-expanded")) {
    document.body.classList.add("player-expanded");
  }
});

let state = {current: null, elapsed: 0, paused: false, queue: [], libraries: [], all_libraries: [], voice_users: [], has_discord_secret: false, has_discord_token: false};
let lastArtId = "";
let lastQueueKey = null;
let lastLibsKey = null;
let lastAllLibsKey = null;
let lastVoiceUsersKey = null;
let lastRolesKey = null;
let volDragging = false;
let searchResults = [];
let userPlaylists = [];
let playlistTracks = [];
let activePlaylist = null;

function updateProgressUI() {
  const cur = state.current;
  if (!cur) {
    document.getElementById("t-cur").textContent = "0:00";
    document.getElementById("t-dur").textContent = "0:00";
    document.getElementById("bar-fill").style.width = "0%";
    return;
  }
  const dur = Math.floor((cur.duration || 0) / 1000);
  const el = Math.min(dur || state.elapsed, state.elapsed || 0);
  document.getElementById("t-cur").textContent = fmt(el);
  document.getElementById("t-dur").textContent = fmt(dur);
  document.getElementById("bar-fill").style.width = (dur > 0 ? Math.min(100, (el / dur) * 100) : 0) + "%";
}

function render(st) {
  state = st;
  stateLoaded = true;
  if (st.guild_id) guildId = String(st.guild_id);
  if (st.channel_id) channelId = String(st.channel_id);
  document.getElementById("srv").textContent = st.server_name || "Plex non configurato";
  const isAct = st.mode === "activity";
  document.getElementById("mode-badge").textContent = isAct ? "🎛️ Activity" : "💬 Comandi";
  document.getElementById("cfg-mode-label").textContent = isAct ? "Activity" : "Comandi Slash";
  document.getElementById("cfg-plex-status").textContent = st.has_token ? (st.server_name ? "✅ " + st.server_name : "⚠️ Scegli server") : "❌ Non collegato";

  if (st.has_discord_secret) {
    document.getElementById("cfg-discord-secret").placeholder = "✅ Client Secret configurato (incolla per sostituire)";
  }

  const linkedListeners = (st.voice_users || []).filter(u => u.plex_username);
  const syncBadge = document.getElementById("sync-badge");
  const pill = document.getElementById("listeners-pill");
  if (linkedListeners.length) {
    syncBadge.style.display = "inline-flex";
    syncBadge.textContent = "🎧 Sync Plex (" + linkedListeners.length + ")";
    pill.style.display = "block";
    pill.textContent = "🎧 Su Plex: " + linkedListeners.map(u => u.plex_username).join(", ");
  } else {
    syncBadge.style.display = "none";
    pill.style.display = "none";
  }

  if (!volDragging && document.activeElement !== document.getElementById("vol")) {
    const v = st.volume ?? 100;
    document.getElementById("vol").value = v;
    setVolFill(document.getElementById("vol"));
    document.getElementById("vol-val").textContent = v + "%";
  }
  if (document.activeElement !== document.getElementById("cfg-vol") && st.volume !== undefined) {
    document.getElementById("cfg-vol").value = st.volume;
    document.getElementById("cfg-bit").value = st.bitrate ?? 128;
    document.getElementById("cfg-idle").value = st.idle_seconds ?? 120;
    document.getElementById("cfg-maxq").value = st.max_queue ?? 100;
  }
  if (document.activeElement !== document.getElementById("cfg-addr") && st.address_override !== undefined) {
    document.getElementById("cfg-addr").value = st.address_override || "";
  }

  if (st.dj_only !== undefined) {
    const djCb = document.getElementById("cfg-dj-only");
    if (djCb && document.activeElement !== djCb) {
      djCb.checked = !!st.dj_only;
    }
    const badge = document.getElementById("cfg-perm-badge");
    if (badge) {
      const djLbl = st.dj_role_name ? "Admin + @" + st.dj_role_name : t("cfg_perms_admin_only");
      badge.textContent = st.dj_only ? djLbl : t("cfg_perms_badge_all");
      badge.className = "badge " + (st.dj_only ? "mode-act" : "sync-ok");
    }
  }

  const rolesKey = JSON.stringify([st.roles || [], st.dj_role || ""]);
  if (rolesKey !== lastRolesKey) {
    lastRolesKey = rolesKey;
    const rSel = document.getElementById("cfg-dj-role-sel");
    if (rSel) {
      const curRoleVal = rSel.value || st.dj_role || "";
      rSel.innerHTML = '<option value="">' + t("cfg_perms_role_none") + '</option>';
      (st.roles || []).forEach(r => {
        const o = document.createElement("option");
        o.value = r.id;
        o.textContent = "@" + r.name;
        rSel.appendChild(o);
      });
      rSel.value = curRoleVal;
    }
  }

  const cur = st.current;
  document.body.classList.toggle("is-playing", !!cur && !st.paused);
  document.body.classList.toggle("is-paused", !!cur && !!st.paused);
  updateRpcBadge();
  const eqEl = document.getElementById("eq-overlay");
  const icoPlay = document.getElementById("ico-play");
  const lblPlay = document.getElementById("lbl-play");
  if (st.paused) {
    if (icoPlay) icoPlay.innerHTML = '<path d="M8 5v14l11-7z"/>';
    if (lblPlay) lblPlay.textContent = t("lbl_resume");
  } else {
    if (icoPlay) icoPlay.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>';
    if (lblPlay) lblPlay.textContent = t("lbl_pause");
  }
  if (cur) {
    eqEl.classList.toggle("playing", !st.paused);
    document.getElementById("now-title").textContent = cur.title;
    document.getElementById("now-artist").textContent = cur.artist;
    document.getElementById("now-album").textContent = (cur.album ? cur.album + " · " : "") + cur.library;
    updateProgressUI();
    updateDiscordActivityPresence();
    if (lastArtId !== cur.id) {
      lastArtId = cur.id;
      const artUrl = artUrlFor(cur.id);
      const img = new Image();
      img.onload = () => {
        const w = document.getElementById("art");
        const oldImg = w.querySelector("img");
        if (oldImg) oldImg.remove();
        document.getElementById("art-icon").style.display = "none";
        w.insertBefore(img, eqEl);
        const bg = document.getElementById("ambient-bg");
        bg.style.backgroundImage = `url("${artUrl}")`;
        bg.style.opacity = "1";
      };
      img.onerror = () => {
        const w = document.getElementById("art");
        const oldImg = w.querySelector("img");
        if (oldImg) oldImg.remove();
        document.getElementById("art-icon").style.display = "block";
        document.getElementById("ambient-bg").style.opacity = "0";
      };
      img.src = artUrl;
    }
  } else {
    lastArtId = "";
    eqEl.classList.remove("playing");
    const w = document.getElementById("art");
    const oldImg = w.querySelector("img");
    if (oldImg) oldImg.remove();
    document.getElementById("art-icon").style.display = "block";
    document.getElementById("ambient-bg").style.opacity = "0";
    document.getElementById("now-title").textContent = t("now_empty_title");
    document.getElementById("now-artist").textContent = t("now_empty_sub");
    document.getElementById("now-album").textContent = "";
    updateProgressUI();
    updateDiscordActivityPresence();
  }

  const q = st.queue || [];
  document.getElementById("q-count").textContent = q.length;
  const qKey = guildId + ":" + (cur ? cur.id : "") + ":" + JSON.stringify(q);
  if (qKey !== lastQueueKey) {
    lastQueueKey = qKey;
    const qEl = document.getElementById("view-q");
    const nowRow = cur ? `
      <div class="item is-current">
        <div class="item-thumb" data-art="${esc(artUrlFor(cur.id))}">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </div>
        <div class="item-info">
          <div class="item-title">${esc(cur.title)}</div>
          <div class="item-artist">${esc(cur.artist)}</div>
          <div class="item-meta"><span class="pill-dur">${fmt((cur.duration || 0) / 1000)}</span><span>${t("queue_now_playing_badge")}</span></div>
        </div>
      </div>` : "";
    qEl.innerHTML = nowRow + (q.length ? q.map((t, i) => `
      <div class="item" style="--i:${i}">
        <div class="item-thumb" data-art="${esc(artUrlFor(t.id))}">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </div>
        <div class="item-info">
          <div class="item-title">${i + 1}. ${esc(t.title)}</div>
          <div class="item-artist">${esc(t.artist)}</div>
          <div class="item-meta">
            <span class="pill-dur">${fmt((t.duration || 0) / 1000)}</span>
            <span>${esc(t.album || t.library)}</span>
          </div>
        </div>
        <div class="item-actions">
          <button type="button" class="ok" data-qact="play_now" data-idx="${i}" title="${t("queue_btn_play_now")}">▶ <span class="lbl-hide-xs">${t("btn_now")}</span></button>
          <button type="button" data-qact="top" data-idx="${i}" title="${t("queue_btn_top")}">↑</button>
          <button type="button" class="danger" data-qact="remove" data-idx="${i}" title="${t("queue_btn_remove")}">✕</button>
        </div>
      </div>`).join("") : `
      <div class="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg></div>
        <div class="empty-title">${t("queue_empty_title")}</div>
        <div class="empty-sub">${t("queue_empty_sub")}</div>
      </div>`);
    hydrateThumbs(qEl);
  }

  const vuKey = JSON.stringify([st.voice_users || [], st.presence_live || []]);
  if (vuKey !== lastVoiceUsersKey) {
    lastVoiceUsersKey = vuKey;
    const vUsers = st.voice_users || [];
    const uSel = document.getElementById("user-sel");
    const prevU = (discordUser && String(discordUser.id)) || uSel.value;
    uSel.innerHTML = "";
    vUsers.forEach(u => {
      const o = document.createElement("option");
      o.value = u.id;
      o.textContent = u.name + (u.plex_username ? " (Plex: " + u.plex_username + ")" : "");
      uSel.appendChild(o);
    });
    if (prevU && vUsers.some(u => u.id === prevU)) uSel.value = prevU;

    const plSel = document.getElementById("pl-user-sel");
    const prevPlU = (discordUser && String(discordUser.id)) || plSel.value;
    plSel.innerHTML = "";
    const linkedUsers = vUsers.filter(u => u.plex_username);
    if (linkedUsers.length) {
      linkedUsers.forEach(u => {
        const o = document.createElement("option");
        o.value = u.id;
        o.textContent = "🎧 " + u.plex_username + " (" + u.name + ")";
        plSel.appendChild(o);
      });
      if (prevPlU && linkedUsers.some(u => u.id === prevPlU)) plSel.value = prevPlU;
    } else {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = t("pl_no_users_in_vc");
      plSel.appendChild(o);
    }

    const vuList = document.getElementById("voice-users-list");
    vuList.innerHTML = vUsers.length ? vUsers.map(u => `
      <div class="lib-item">
        <span>👤 <b>${esc(u.name)}</b></span>
        <span style="display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end">
          <span class="badge ${u.rpc ? 'mode-act' : ''}">${u.rpc ? ((st.presence_live || []).includes(u.id) ? '🟣 Presence live' : '🟣 RPC') : 'RPC off'}</span>
          <span class="badge ${u.plex_username ? 'sync-ok' : ''}">${u.plex_username ? 'Plex: ' + esc(u.plex_username) : 'Plex off'}</span>
        </span>
      </div>`).join("") : '<div class="now-sub">${t("acc_listeners_none")}</div>';
  }

  const libsKey = JSON.stringify(st.libraries || []);
  if (libsKey !== lastLibsKey) {
    lastLibsKey = libsKey;
    const sel = document.getElementById("lib-sel");
    const curVal = sel.value;
    sel.innerHTML = '<option value="">' + t("search_all_libs") + '</option>';
    (st.libraries || []).forEach(l => {
      const o = document.createElement("option");
      o.value = l.id;
      o.textContent = l.title;
      sel.appendChild(o);
    });
    sel.value = curVal;
  }

  const allLibsKey = JSON.stringify(st.all_libraries || []);
  if (allLibsKey !== lastAllLibsKey) {
    lastAllLibsKey = allLibsKey;
    const box = document.getElementById("cfg-libs-list");
    const allLibs = st.all_libraries || [];
    box.innerHTML = allLibs.length ? allLibs.map(l => `
      <div class="lib-item">
        <span><b>${esc(l.title)}</b> (ID: ${esc(l.id)})</span>
        <button type="button" class="${l.enabled ? 'ok' : ''}" data-libid="${esc(l.id)}" data-enabled="${l.enabled ? '0' : '1'}">
          ${l.enabled ? t("cfg_lib_enabled") : t("cfg_lib_disabled")}
        </button>
      </div>`).join("") : '<div class="now-sub">${t("cfg_libs_none")}</div>';
  }

  if (st.language && st.language !== currentLang && !localStorage.getItem("plexcord_lang_manual")) {
    applyLang(st.language);
  }
}

async function act(action, extra = {}, silent = false) {
  try {
    const payload = {action, ...extra};
    if (!payload.user_id) {
      if (discordUser && discordUser.id) {
        payload.user_id = String(discordUser.id);
      } else {
        const uSel = document.getElementById("user-sel");
        if (uSel && uSel.value) payload.user_id = uSel.value;
      }
    }
    const r = await fetch(apiPath("api/control"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (!r.ok) { if (!silent) msg("⚠️ " + (data.error || "Errore")); return null; }
    if (data.message && !silent) msg(data.message);
    if (data.state) render(data.state);
    return data;
  } catch {
    if (!silent) msg("⚠️ Connessione al bot non riuscita.");
    return null;
  }
}

async function cfgAct(action, extra = {}, silent = false) {
  try {
    const payload = {action, ...extra};
    if (!payload.user_id) {
      if (discordUser && discordUser.id) {
        payload.user_id = String(discordUser.id);
      } else {
        const uSel = document.getElementById("user-sel");
        if (uSel && uSel.value) payload.user_id = uSel.value;
      }
    }
    const r = await fetch(apiPath("api/config"), {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (!r.ok) { if (!silent) msg("⚠️ " + (data.error || "Errore")); return null; }
    if (data.message && !silent) msg(data.message);
    if (data.state) render(data.state);
    return data;
  } catch {
    if (!silent) msg("⚠️ Errore di connessione al bot.");
    return null;
  }
}

// Controlli principali del player
document.getElementById("btn-restart").addEventListener("click", () => act("seek", {seconds: 0}));
document.getElementById("btn-play").addEventListener("click", () => act("toggle"));
document.getElementById("btn-skip").addEventListener("click", () => act("skip"));
document.getElementById("btn-shuffle").addEventListener("click", () => act("shuffle"));
document.getElementById("btn-stop").addEventListener("click", () => act("stop"));
document.getElementById("btn-leave").addEventListener("click", () => act("leave"));

document.getElementById("seek-bar").addEventListener("click", (e) => {
  if (!state.current || !state.current.duration) return;
  const rect = e.currentTarget.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const seconds = Math.floor(ratio * (state.current.duration / 1000));
  act("seek", {seconds});
});

// Controlli Volume in tempo reale (senza interrompere la riproduzione)
const volEl = document.getElementById("vol");
let volLiveTimer = null;
volEl.addEventListener("pointerdown", () => { volDragging = true; });
volEl.addEventListener("input", () => {
  setVolFill(volEl);
  document.getElementById("vol-val").textContent = volEl.value + "%";
  if (!volLiveTimer) {
    volLiveTimer = setTimeout(() => {
      volLiveTimer = null;
      act("volume", {volume: Number(volEl.value)}, true);
    }, 100);
  }
});
volEl.addEventListener("change", () => {
  volDragging = false;
  clearTimeout(volLiveTimer);
  volLiveTimer = null;
  act("volume", {volume: Number(volEl.value)});
});
document.getElementById("btn-voldown").addEventListener("click", () => {
  const v = Math.max(0, Number(volEl.value) - 10);
  volEl.value = v;
  setVolFill(volEl);
  document.getElementById("vol-val").textContent = v + "%";
  act("volume", {volume: v});
});
document.getElementById("btn-volup").addEventListener("click", () => {
  const v = Math.min(150, Number(volEl.value) + 10);
  volEl.value = v;
  setVolFill(volEl);
  document.getElementById("vol-val").textContent = v + "%";
  act("volume", {volume: v});
});

// Event delegation per la Coda
document.getElementById("view-q").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-qact]");
  if (!btn) return;
  const idx = Number(btn.dataset.idx);
  const qact = btn.dataset.qact;
  if (qact === "play_now") act("promote", {index: idx, play_now: true});
  else if (qact === "top") act("promote", {index: idx, play_now: false});
  else if (qact === "remove") act("remove", {index: idx});
});

// Gestione Playlist Personali Plex
function currentPlUserId() {
  const selVal = document.getElementById("pl-user-sel").value;
  if (selVal) return selVal;
  if (discordUser && discordUser.id) return String(discordUser.id);
  const linked = (state.voice_users || []).find(u => u.plex_username);
  return linked ? linked.id : "";
}

function renderPlaylistList() {
  activePlaylist = null;
  document.getElementById("pl-header-bar").style.display = "flex";
  document.getElementById("pl-detail-bar").style.display = "none";
  const list = document.getElementById("p-list");
  if (!userPlaylists.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-title">Nessuna playlist trovata</div><div class="empty-sub">Non ci sono playlist audio sul tuo account Plex.</div></div>';
    return;
  }
  list.innerHTML = userPlaylists.map((p, i) => `
    <div class="item" style="--i:${i}">
      <div class="item-thumb" data-art="${esc(artUrlFor('pl_' + p.id))}">
        <svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg>
      </div>
      <div class="item-info" style="cursor:pointer" data-pact="open" data-idx="${i}">
        <div class="item-title">${esc(p.title)}</div>
        <div class="item-artist">${t("pl_tracks_label", {count: p.track_count})}</div>
        <div class="item-meta">
          <span class="pill-dur">${fmt((p.duration || 0) / 1000)}</span>
          <span>${t("pl_tap_to_open")}</span>
        </div>
      </div>
      <div class="item-actions">
        <button type="button" class="ok" data-pact="play" data-idx="${i}" title="${t("pl_btn_play_all")}">▶ <span class="lbl-hide-xs">${t("btn_now")}</span></button>
        <button type="button" data-pact="shuffle" data-idx="${i}" title="${t("pl_btn_shuffle_all")}">🔀</button>
        <button type="button" class="primary" data-pact="queue" data-idx="${i}" title="${t("pl_btn_queue_all")}">+ <span class="lbl-hide-xs">${t("btn_queue")}</span></button>
        <button type="button" data-pact="open" data-idx="${i}" title="${t("pl_tap_to_open")}">📂</button>
      </div>
    </div>`).join("");
  hydrateThumbs(list);
}

async function loadPlaylists() {
  const uid = currentPlUserId();
  const list = document.getElementById("p-list");
  activePlaylist = null;
  document.getElementById("pl-header-bar").style.display = "flex";
  document.getElementById("pl-detail-bar").style.display = "none";
  if (!uid) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z"/></svg></div>
        <div class="empty-title">Collega il tuo Account Plex</div>
        <div class="empty-sub">Accedi con il codice PIN a 4 cifre nella scheda <b>Account</b> per sfogliare e riprodurre le tue playlist personali.</div>
        <button type="button" class="primary" id="btn-go-link-plex" style="margin-top:6px">🔑 Collega Account Plex</button>
      </div>`;
    const goBtn = document.getElementById("btn-go-link-plex");
    if (goBtn) goBtn.addEventListener("click", () => showTab("u"));
    return;
  }
  list.innerHTML = skeletonRows(5);
  try {
    const u = new URLSearchParams({guild_id: guildId, channel_id: channelId, token, discord_id: uid});
    const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
    const r = await fetch(base + "api/playlists?" + u.toString());
    const data = await r.json();
    if (!r.ok) {
      list.innerHTML = `<div class="empty-state"><div class="empty-sub">⚠️ ${esc(data.error || "Errore caricamento playlist")}</div></div>`;
      return;
    }
    if (!data.linked) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-title">Account Plex non ancora collegato</div>
          <div class="empty-sub">${esc(data.error || "Collega il tuo account Plex nella scheda 'Account'.")}</div>
          <button type="button" class="primary" id="btn-go-link-plex2" style="margin-top:6px">🔑 Collega Account Plex</button>
        </div>`;
      const goBtn = document.getElementById("btn-go-link-plex2");
      if (goBtn) goBtn.addEventListener("click", () => showTab("u"));
      return;
    }
    userPlaylists = data.playlists || [];
    renderPlaylistList();
  } catch {
    list.innerHTML = '<div class="empty-state"><div class="empty-sub">⚠️ Errore di rete durante il caricamento delle playlist.</div></div>';
  }
}

async function openPlaylist(pl) {
  if (!pl) return;
  activePlaylist = pl;
  document.getElementById("pl-header-bar").style.display = "none";
  document.getElementById("pl-detail-bar").style.display = "flex";
  document.getElementById("pl-detail-title").textContent = pl.title + " (" + pl.track_count + ")";
  const list = document.getElementById("p-list");
  list.innerHTML = skeletonRows(8);
  try {
    const uid = currentPlUserId();
    const u = new URLSearchParams({guild_id: guildId, channel_id: channelId, token, playlist_id: pl.id, discord_id: uid});
    const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
    const r = await fetch(base + "api/playlist_tracks?" + u.toString());
    const data = await r.json();
    if (!r.ok) {
      list.innerHTML = `<div class="empty-state"><div class="empty-sub">⚠️ ${esc(data.error || "Errore")}</div></div>`;
      return;
    }
    playlistTracks = data.tracks || [];
    list.innerHTML = playlistTracks.length ? playlistTracks.map((t, i) => `
      <div class="item${state.current && state.current.id === t.id ? ' is-current' : ''}" style="--i:${i}">
        <div class="item-thumb" data-art="${esc(artUrlFor(t.id))}" data-play="1" data-ptact="now" data-idx="${i}" title="Riproduci subito">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </div>
        <div class="item-info">
          <div class="item-title">${i + 1}. ${esc(t.title)}</div>
          <div class="item-artist">${esc(t.artist)}</div>
          <div class="item-meta">
            <span class="pill-dur">${fmt((t.duration || 0) / 1000)}</span>
            <span>${esc(t.album || t.library)}</span>
          </div>
        </div>
        <div class="item-actions">
          <button type="button" class="ok" data-ptact="now" data-idx="${i}" title="Riproduci subito">▶ <span class="lbl-hide-xs">Ora</span></button>
          <button type="button" class="primary" data-ptact="queue" data-idx="${i}" title="Aggiungi alla coda">+ <span class="lbl-hide-xs">Coda</span></button>
        </div>
      </div>`).join("") : '<div class="empty-state"><div class="empty-sub">Questa playlist è vuota.</div></div>';
    hydrateThumbs(list);
  } catch {
    list.innerHTML = '<div class="empty-state"><div class="empty-sub">⚠️ Errore di rete.</div></div>';
  }
}

document.getElementById("pl-user-sel").addEventListener("change", loadPlaylists);
document.getElementById("btn-pl-refresh").addEventListener("click", loadPlaylists);
document.getElementById("btn-pl-back").addEventListener("click", renderPlaylistList);
document.getElementById("btn-pl-play-all").addEventListener("click", () => {
  if (activePlaylist) act("play_playlist", {playlist_id: activePlaylist.id, discord_id: currentPlUserId(), play_now: true, shuffle: false});
});
document.getElementById("btn-pl-shuffle-all").addEventListener("click", () => {
  if (activePlaylist) act("play_playlist", {playlist_id: activePlaylist.id, discord_id: currentPlUserId(), play_now: true, shuffle: true});
});
document.getElementById("btn-pl-queue-all").addEventListener("click", () => {
  if (activePlaylist) act("play_playlist", {playlist_id: activePlaylist.id, discord_id: currentPlUserId(), play_now: false, shuffle: false});
});

document.getElementById("p-list").addEventListener("click", (e) => {
  const pEl = e.target.closest("[data-pact]");
  if (pEl) {
    const pl = userPlaylists[Number(pEl.dataset.idx)];
    if (!pl) return;
    const pact = pEl.dataset.pact;
    const uid = currentPlUserId();
    if (pact === "open") openPlaylist(pl);
    else if (pact === "play") act("play_playlist", {playlist_id: pl.id, discord_id: uid, play_now: true, shuffle: false});
    else if (pact === "shuffle") act("play_playlist", {playlist_id: pl.id, discord_id: uid, play_now: true, shuffle: true});
    else if (pact === "queue") act("play_playlist", {playlist_id: pl.id, discord_id: uid, play_now: false, shuffle: false});
    return;
  }
  const tBtn = e.target.closest("[data-ptact]");
  if (tBtn) {
    const track = playlistTracks[Number(tBtn.dataset.idx)];
    if (!track) return;
    act("play", {track, play_now: tBtn.dataset.ptact === "now"});
  }
});

// Ricerca brani con copertina
let searchTimer = null;
document.getElementById("q-in").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(doSearch, 300);
});
document.getElementById("q-in").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { clearTimeout(searchTimer); doSearch(); }
});
document.getElementById("lib-sel").addEventListener("change", doSearch);
document.getElementById("btn-search").addEventListener("click", doSearch);

async function doSearch() {
  const q = document.getElementById("q-in").value.trim();
  const lib = document.getElementById("lib-sel").value;
  const list = document.getElementById("s-list");
  if (!q) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg></div>
        <div class="empty-title">Esplora la tua libreria Plex</div>
        <div class="empty-sub">Digita il titolo di una canzone o il nome di un artista per cercare con anteprima copertina.</div>
      </div>`;
    return;
  }
  list.innerHTML = skeletonRows(7);
  try {
    const u = new URLSearchParams({guild_id: guildId, channel_id: channelId, token, query: q, library: lib});
    const base = location.pathname.endsWith("/") ? location.pathname : location.pathname + "/";
    const r = await fetch(base + "api/search?" + u.toString());
    const data = await r.json();
    if (!r.ok) {
      list.innerHTML = `<div class="empty-state"><div class="empty-sub">⚠️ ${esc(data.error)}</div></div>`;
      return;
    }
    searchResults = data.tracks || [];
    list.innerHTML = searchResults.length ? searchResults.map((t, i) => `
      <div class="item${state.current && state.current.id === t.id ? ' is-current' : ''}" style="--i:${i}">
        <div class="item-thumb" data-art="${esc(artUrlFor(t.id))}" data-play="1" data-sact="now" data-idx="${i}" title="${t("btn_now")}">
          <svg viewBox="0 0 24 24"><path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6Z"/></svg>
        </div>
        <div class="item-info">
          <div class="item-title">${esc(t.title)}</div>
          <div class="item-artist">${esc(t.artist)}</div>
          <div class="item-meta">
            <span class="pill-dur">${fmt((t.duration || 0) / 1000)}</span>
            <span>${esc(t.album ? t.album + ' · ' + t.library : t.library)}</span>
          </div>
        </div>
        <div class="item-actions">
          <button type="button" class="ok" data-sact="now" data-idx="${i}" title="${t("btn_now")}">▶ <span class="lbl-hide-xs">${t("btn_now")}</span></button>
          <button type="button" class="primary" data-sact="queue" data-idx="${i}" title="${t("btn_queue")}">+ <span class="lbl-hide-xs">${t("btn_queue")}</span></button>
        </div>
      </div>`).join("") : `<div class="empty-state"><div class="empty-title">${t("search_no_results_title")}</div><div class="empty-sub">${t("search_no_results_sub")}</div></div>`;
    hydrateThumbs(list);
  } catch {
    list.innerHTML = `<div class="empty-state"><div class="empty-sub">${t("search_network_err")}</div></div>`;
  }
}

document.getElementById("s-list").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-sact]");
  if (!btn) return;
  const track = searchResults[Number(btn.dataset.idx)];
  if (!track) return;
  const playNow = btn.dataset.sact === "now";
  act("play", {track, play_now: playNow});
});

// Salvataggio Discord Client Secret per RPC
document.getElementById("btn-save-secret").addEventListener("click", async () => {
  const sec = document.getElementById("cfg-discord-secret").value.trim();
  if (!sec) { msg("⚠️ Incolla il Client Secret di Discord."); return; }
  const d = await cfgAct("save_discord_secret", {client_secret: sec});
  if (d) {
    document.getElementById("cfg-discord-secret").value = "";
    authorizeDiscordRpc(true);
  }
});

// Collegamento Account Personale Plex <-> Discord (PIN 4 cifre + auto-polling)
let userPinPoll = null;
document.getElementById("btn-user-pin").addEventListener("click", async () => {
  const uid = document.getElementById("user-sel").value;
  if (!uid) { msg("⚠️ Entra nel canale vocale e seleziona il tuo utente Discord."); return; }
  const d = await cfgAct("user_pin", {discord_id: uid});
  if (d && d.code) {
    document.getElementById("user-pin-code").textContent = d.code;
    document.getElementById("user-pin-box").style.display = "flex";
    clearInterval(userPinPoll);
    userPinPoll = setInterval(async () => {
      const chk = await cfgAct("user_check_pin", {discord_id: uid}, true);
      if (chk && chk.ok) {
        clearInterval(userPinPoll);
        document.getElementById("user-pin-box").style.display = "none";
        msg(chk.message || "✅ Account Plex collegato!");
      }
    }, 3000);
  }
});
document.getElementById("btn-user-open-link").addEventListener("click", () => openExternalUrl("https://plex.tv/link"));
async function copyUserPin() {
  const c = document.getElementById("user-pin-code").textContent.trim();
  const ok = await copyText(c);
  msg(ok ? "📋 Codice " + c + " copiato negli appunti!" : "📋 Codice PIN: " + c);
}
document.getElementById("btn-user-copy").addEventListener("click", copyUserPin);
document.getElementById("user-pin-code").addEventListener("click", copyUserPin);
document.getElementById("btn-user-check").addEventListener("click", async () => {
  const uid = document.getElementById("user-sel").value;
  const chk = await cfgAct("user_check_pin", {discord_id: uid});
  if (chk && chk.ok) {
    clearInterval(userPinPoll);
    document.getElementById("user-pin-box").style.display = "none";
  }
});
document.getElementById("btn-user-unlink").addEventListener("click", () => {
  const uid = document.getElementById("user-sel").value;
  if (!uid) return;
  clearInterval(userPinPoll);
  document.getElementById("user-pin-box").style.display = "none";
  cfgAct("user_unlink", {discord_id: uid});
});

// Eventi scheda Configurazione Server (PIN 4 cifre + auto-polling)
let srvPinPoll = null;
document.getElementById("btn-mode-activity").addEventListener("click", () => cfgAct("set_mode", {mode: "activity"}));
document.getElementById("btn-mode-commands").addEventListener("click", () => cfgAct("set_mode", {mode: "commands"}));

document.getElementById("btn-plex-login").addEventListener("click", async () => {
  const d = await cfgAct("plex_pin");
  if (d && d.code) {
    document.getElementById("plex-pin-code").textContent = d.code;
    document.getElementById("plex-pin-box").style.display = "flex";
    clearInterval(srvPinPoll);
    srvPinPoll = setInterval(async () => {
      const chk = await cfgAct("plex_check_pin", {}, true);
      if (chk && chk.ok) {
        clearInterval(srvPinPoll);
        document.getElementById("plex-pin-box").style.display = "none";
        msg(chk.message || "✅ Login Plex completato!");
        loadPlexServers();
      }
    }, 3000);
  }
});
document.getElementById("btn-plex-open-link").addEventListener("click", () => openExternalUrl("https://plex.tv/link"));
async function copySrvPin() {
  const c = document.getElementById("plex-pin-code").textContent.trim();
  const ok = await copyText(c);
  msg(ok ? "📋 Codice " + c + " copiato negli appunti!" : "📋 Codice PIN: " + c);
}
document.getElementById("btn-plex-copy").addEventListener("click", copySrvPin);
document.getElementById("plex-pin-code").addEventListener("click", copySrvPin);
document.getElementById("btn-plex-complete").addEventListener("click", async () => {
  const d = await cfgAct("plex_check_pin");
  if (d && d.ok) {
    clearInterval(srvPinPoll);
    document.getElementById("plex-pin-box").style.display = "none";
    loadPlexServers();
  }
});
document.getElementById("btn-plex-logout").addEventListener("click", () => {
  clearInterval(srvPinPoll);
  document.getElementById("plex-pin-box").style.display = "none";
  cfgAct("plex_logout");
});

async function loadPlexServers() {
  const d = await cfgAct("plex_servers");
  if (!d || !d.servers) return;
  const sel = document.getElementById("cfg-server-sel");
  sel.innerHTML = "";
  d.servers.forEach(s => {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = s.name + " (" + s.id.slice(0, 8) + ")";
    if (s.selected) o.selected = true;
    sel.appendChild(o);
  });
}
document.getElementById("btn-load-servers").addEventListener("click", loadPlexServers);
document.getElementById("btn-save-addr").addEventListener("click", () => {
  cfgAct("plex_address", {url: document.getElementById("cfg-addr").value.trim()});
});
document.getElementById("btn-select-server").addEventListener("click", () => {
  const id = document.getElementById("cfg-server-sel").value;
  if (!id) { msg("⚠️ Carica e seleziona prima un server Plex."); return; }
  cfgAct("plex_server", {server_id: id});
});
document.getElementById("btn-libs-all").addEventListener("click", () => cfgAct("plex_all_libraries"));
document.getElementById("cfg-libs-list").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-libid]");
  if (!btn) return;
  cfgAct("plex_library", {library_id: btn.dataset.libid, enabled: btn.dataset.enabled === "1"});
});
document.getElementById("btn-save-perms")?.addEventListener("click", () => {
  cfgAct("save_settings", {
    dj_only: document.getElementById("cfg-dj-only").checked,
    dj_role: document.getElementById("cfg-dj-role-sel").value
  });
});
document.getElementById("cfg-dj-only")?.addEventListener("change", (e) => {
  const isChecked = e.target.checked;
  const badge = document.getElementById("cfg-perm-badge");
  if (badge) {
    badge.textContent = isChecked ? "Admin & DJ" : "Tutti";
    badge.className = "badge " + (isChecked ? "mode-act" : "sync-ok");
  }
});
document.getElementById("btn-save-settings").addEventListener("click", () => {
  cfgAct("save_settings", {
    volume: Number(document.getElementById("cfg-vol").value),
    bitrate: Number(document.getElementById("cfg-bit").value),
    idle_seconds: Number(document.getElementById("cfg-idle").value),
    max_queue: Number(document.getElementById("cfg-maxq").value),
    dj_only: document.getElementById("cfg-dj-only").checked,
    dj_role: document.getElementById("cfg-dj-role-sel").value
  });
});

function connectWs() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(proto + "//" + location.host + apiPath("api/ws"));
  ws.onmessage = (ev) => {
    try { render(JSON.parse(ev.data)); } catch {}
  };
  ws.onclose = () => setTimeout(connectWs, 2500);
}
fetch(apiPath("api/state")).then(r => r.json()).then(d => { if (!d.error) render(d); }).catch(() => {});
connectWs();
updateReducedMode();
applyLang(currentLang);

document.getElementById("btn-save-lang")?.addEventListener("click", async () => {
  const l = document.getElementById("cfg-lang-sel").value;
  try { localStorage.setItem("plexcord_lang_manual", "1"); } catch {}
  applyLang(l);
  const res = await cfgAct("save_settings", {language: l});
  if (res) msg(t("toast_lang_saved"));
});
document.getElementById("cfg-lang-sel")?.addEventListener("change", (e) => {
  const l = e.target.value;
  try { localStorage.setItem("plexcord_lang_manual", "1"); } catch {}
  applyLang(l);
});

setInterval(() => {
  if (state.current && !state.paused) {
    state.elapsed = (state.elapsed || 0) + 1;
    updateProgressUI();
  }
}, 1000);
</script>
</body>
</html>
"""


class ActivityServer:
    """Server HTTP/WebSocket ultraleggero per Discord Embedded App SDK / Web Player."""

    def __init__(self, bot, host: str = "0.0.0.0", port: int = 8080):
        self.bot = bot
        self.host = host
        self.port = port
        self.secret = bot.store.client_id.encode()
        self.runner: web.AppRunner | None = None
        self.art_cache: dict[tuple[int, str], tuple[bytes, str]] = {}
        self.lib_cache: dict[int, tuple[int, list]] = {}
        self.user_name_cache: dict[int, str] = {}
        self.pending_pins: dict[int, int] = {}
        self.pending_user_pins: dict[int, tuple[int, str]] = {}
        self._logo_bytes: bytes | None = None
        self._banner_bytes: bytes | None = None


    def _load_asset(self, filename: str) -> bytes | None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates = [
            os.path.join("icon", filename),
            os.path.join(base_dir, "icon", filename),
            os.path.join("/app", "icon", filename),
        ]
        for c in candidates:
            if os.path.isfile(c):
                try:
                    with open(c, "rb") as f:
                        return f.read()
                except Exception:
                    pass
        return None

    async def logo_handler(self, request: web.Request):
        if self._logo_bytes is None:
            self._logo_bytes = self._load_asset("logo.jpg")
        if self._logo_bytes:
            return web.Response(body=self._logo_bytes, content_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        return web.Response(status=404)

    async def banner_handler(self, request: web.Request):
        if self._banner_bytes is None:
            self._banner_bytes = self._load_asset("banner.jpg")
        if self._banner_bytes:
            return web.Response(body=self._banner_bytes, content_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
        return web.Response(status=404)

    def _discord_secret(self) -> str:
        env_sec = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
        if env_sec:
            return env_sec
        if hasattr(self.bot.store, "get_meta"):
            return self.bot.store.get_meta("discord_client_secret", "")
        return ""

    def sign(self, guild_id: int, channel_id: int) -> str:
        exp = int(time.time()) + 86400
        payload = f"{guild_id}:{channel_id}:{exp}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
        return f"{payload}:{sig}"

    def _channel_has_humans(self, vc) -> bool:
        bot_id = getattr(getattr(self.bot, "user", None), "id", None)
        voice_states = getattr(vc, "voice_states", None)
        if isinstance(voice_states, dict) and any(uid != bot_id for uid in voice_states):
            return True
        members = getattr(vc, "members", None)
        if members and any(not getattr(m, "bot", False) for m in members):
            return True
        return False

    async def _voice_users(self, guild, channel) -> list[dict]:
        if not channel:
            return []
        bot_id = getattr(getattr(self.bot, "user", None), "id", None)
        user_map: dict[int, str] = {}
        for m in getattr(channel, "members", []) or []:
            if not getattr(m, "bot", False):
                name = getattr(m, "display_name", None) or getattr(m, "name", f"Utente {m.id}")
                user_map[m.id] = name
                self.user_name_cache[m.id] = name
        vs = getattr(channel, "voice_states", None)
        if isinstance(vs, dict):
            for uid in vs:
                if uid == bot_id or uid in user_map:
                    continue
                if uid in self.user_name_cache:
                    user_map[uid] = self.user_name_cache[uid]
                    continue
                member = guild.get_member(uid) if hasattr(guild, "get_member") else None
                if not member and hasattr(guild, "fetch_member"):
                    with contextlib.suppress(Exception):
                        member = await guild.fetch_member(uid)
                if member and getattr(member, "bot", False):
                    continue
                name = getattr(member, "display_name", None) or getattr(member, "name", f"Utente {uid}")
                self.user_name_cache[uid] = name
                user_map[uid] = name
        links = {
            u.discord_id: u
            for u in (self.bot.store.list_users(list(user_map.keys())) if hasattr(self.bot.store, "list_users") else [])
        }
        rpc_ids = set(
            self.bot.store.discord_oauth_ids(list(user_map.keys()))
            if hasattr(self.bot.store, "discord_oauth_ids") else []
        )
        return [
            {
                "id": str(uid),
                "name": name,
                "plex_username": links[uid].plex_username if uid in links else "",
                "rpc": uid in rpc_ids,
            }
            for uid, name in user_map.items()
        ]

    def resolve_context(self, request: web.Request, *, require_active: bool = False):
        token = request.query.get("token", "")
        guild_id = 0
        channel_id = 0
        if token:
            parts = token.split(":")
            if len(parts) != 4 or not parts[0].isdigit() or not parts[1].isdigit() or not parts[2].isdigit():
                raise PlexError("Token di sessione non valido. Usa /activity su Discord.")
            payload = ":".join(parts[:3])
            expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
            if not hmac.compare_digest(parts[3], expected) or int(parts[2]) < int(time.time()):
                raise PlexError("Sessione scaduta o non valida. Usa /activity su Discord.")
            guild_id, channel_id = int(parts[0]), int(parts[1])
        else:
            raw_guild = request.query.get("guild_id", "")
            if not raw_guild or raw_guild == "0":
                raw_guild = request.match_info.get("guild_id", "")
            raw_channel = request.query.get("channel_id", "")
            if raw_guild.isdigit():
                guild_id = int(raw_guild)
            if raw_channel.isdigit():
                channel_id = int(raw_channel)
            if not guild_id:
                for g in self.bot.guilds:
                    if getattr(g, "voice_client", None):
                        guild_id = g.id
                        break
                if not guild_id:
                    for g in self.bot.guilds:
                        if any(self._channel_has_humans(vc) for vc in getattr(g, "voice_channels", [])):
                            guild_id = g.id
                            break
                if not guild_id and self.bot.guilds:
                    guild_id = self.bot.guilds[0].id
        guild = self.bot.get_guild(guild_id) if guild_id else None
        if not guild:
            raise PlexError("Apri l'Activity da un canale vocale del server Discord o usa /activity.")
        voice = getattr(guild, "voice_client", None)
        channel = guild.get_channel(channel_id) if channel_id and hasattr(guild, "get_channel") else None
        if voice and getattr(voice, "channel", None):
            channel = voice.channel
        if not channel:
            for vc in getattr(guild, "voice_channels", []):
                if self._channel_has_humans(vc):
                    channel = vc
                    break
        if require_active and not channel:
            raise PlexError("Entra in un canale vocale su Discord per riprodurre la musica.")
        if require_active and not voice and channel:
            has_voice_tracking = hasattr(channel, "voice_states") or hasattr(channel, "members")
            if has_voice_tracking and not self._channel_has_humans(channel):
                raise PlexError("Deve esserci almeno un utente nel canale vocale per controllare la musica.")
        return guild, channel

    async def _get_libraries(self, guild_id: int, settings):
        if not settings.server_url or not settings.server_token:
            return []
        cached = self.lib_cache.get(guild_id)
        if cached and cached[0] == settings.revision:
            return cached[1]
        with contextlib.suppress(Exception):
            libs = await self.bot.plex.libraries(settings)
            self.lib_cache[guild_id] = (settings.revision, libs)
            return libs
        return []

    async def build_state(self, guild, channel=None):
        settings = self.bot.store.get(guild.id)
        player = self.bot.players.get(guild.id)
        all_libs = await self._get_libraries(guild.id, settings)
        enabled_libs = [
            {"id": lib.id, "title": lib.title}
            for lib in all_libs
            if settings.libraries is None or lib.id in settings.libraries
        ]
        all_libs_info = [
            {
                "id": lib.id,
                "title": lib.title,
                "enabled": settings.libraries is None or lib.id in settings.libraries,
            }
            for lib in all_libs
        ]
        voice_users = await self._voice_users(guild, channel)
        presence = getattr(self.bot, "presence", None)
        dj_role_obj = guild.get_role(settings.dj_role) if settings.dj_role and hasattr(guild, "get_role") else None
        roles = []
        if hasattr(guild, "roles"):
            roles = [
                {"id": str(r.id), "name": r.name}
                for r in sorted(guild.roles, key=lambda x: getattr(x, "position", 0), reverse=True)
                if not (hasattr(r, "is_default") and r.is_default()) and not getattr(r, "managed", False)
            ]
        return {
            "guild_id": str(guild.id),
            "channel_id": str(channel.id) if channel else "",
            "server_name": settings.server_name or "",
            "language": getattr(settings, "language", "en") or "en",
            "has_token": bool(settings.token),
            "has_discord_secret": bool(self._discord_secret()),
            "has_discord_token": any(u.get("rpc") for u in voice_users),
            "public_url": bool(getattr(self.bot, "activity_url", "")),
            "address_override": settings.address_override,
            "mode": settings.mode,
            "volume": settings.volume,
            "bitrate": settings.bitrate,
            "idle_seconds": settings.idle_seconds,
            "max_queue": settings.max_queue,
            "dj_only": bool(settings.dj_only),
            "dj_role": str(settings.dj_role or ""),
            "dj_role_name": dj_role_obj.name if dj_role_obj else "",
            "roles": roles,
            "paused": bool(player and player.paused_at),
            "elapsed": player.elapsed if player else 0,
            "current": asdict(player.current) if player and player.current else None,
            "queue": [asdict(t) for t in player.queue] if player else [],
            "libraries": enabled_libs,
            "all_libraries": all_libs_info,
            "voice_users": voice_users,
            "presence_live": presence.active_for(int(u["id"]) for u in voice_users) if presence else [],
        }

    async def index(self, request: web.Request):
        bot_uid = getattr(getattr(self.bot, "user", None), "id", "")
        client_id = str(self.bot.application_id or os.environ.get("DISCORD_CLIENT_ID", "") or bot_uid or "")
        html = ACTIVITY_HTML.replace("__CLIENT_ID__", client_id)
        return web.Response(text=html, content_type="text/html")

    async def discord_token_handler(self, request: web.Request):
        """OAuth2 Discord per singolo utente: i token restano sul server, il client riceve
        solo il proprio access_token e una chiave opaca per ripristinarlo in seguito."""
        presence = getattr(self.bot, "presence", None)
        try:
            if presence is None:
                raise PlexError("Rich Presence non disponibile.")
            data = await request.json()
            action = str(data.get("action") or "exchange").strip()
            raw_uid = str(data.get("user_id") or "").strip()
            key = str(data.get("key") or "").strip()

            if action in ("restore", "revoke"):
                if not raw_uid.isdigit() or not presence.check_user_key(int(raw_uid), key):
                    return web.json_response({"access_token": ""})
                uid = int(raw_uid)
                if action == "revoke":
                    await presence.revoke(uid)
                    return web.json_response({"ok": True, "message": "🗑️ Rich Presence disattivato per il tuo profilo."})
                token = await presence.access_token(uid, force_refresh=bool(data.get("refresh")))
                return web.json_response({
                    "access_token": token,
                    "server_presence": presence.has_scope(uid) and uid not in presence.unsupported,
                })

            code = str(data.get("code") or "").strip()
            if not code or not presence.client_secret():
                raise PlexError("Configura prima il Discord Client Secret nella scheda 'Account'.")
            try:
                payload, user = await presence.exchange(code)
            except ValueError as error:
                detail = str(error).strip()
                suffix = f" ({detail[:120]})" if detail else ""
                raise PlexError(
                    f"Autorizzazione OAuth2 Discord fallita{suffix}. Verifica Client Secret e Redirect URL su Discord Developer Portal."
                ) from None
            uid = int(user["id"])
            name = str(user.get("global_name") or user.get("username") or "")[:80]
            if name:
                self.user_name_cache[uid] = name
            for player in list(getattr(self.bot, "players", {}).values()):
                if player.current:
                    presence.notify(player, None)
            return web.json_response({
                "access_token": payload["access_token"],
                "user_id": str(uid),
                "key": presence.user_key(uid),
                "server_presence": presence.has_scope(uid),
            })
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Errore durante lo scambio del token Discord."}, status=400)

    async def state_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request)
            return web.json_response(await self.build_state(guild, channel))
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)

    def _resolve_user_link(self, guild, channel, raw_uid: str = ""):
        if not hasattr(self.bot.store, "get_user"):
            return None
        uid_str = str(raw_uid or "").strip()
        if uid_str.isdigit():
            link = self.bot.store.get_user(int(uid_str))
            if link and link.plex_token:
                return link
        if channel and hasattr(self.bot.store, "list_users"):
            ids = set()
            vs = getattr(channel, "voice_states", None)
            if isinstance(vs, dict):
                ids.update(vs.keys())
            for m in getattr(channel, "members", []) or []:
                if not getattr(m, "bot", False):
                    ids.add(m.id)
            links = self.bot.store.list_users(list(ids))
            if links:
                return links[0]
        return None

    async def playlists_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request)
            raw_uid = request.query.get("discord_id", "").strip()
            link = self._resolve_user_link(guild, channel, raw_uid)
            if not link:
                return web.json_response({
                    "linked": False,
                    "playlists": [],
                    "error": "Collega prima il tuo account Plex nella scheda '🎧 RPC & Account' per vedere le tue playlist personali.",
                })
            settings = self.bot.store.get(guild.id)
            playlists = await self.bot.plex.playlists(settings, user_token=link.plex_token)
            return web.json_response({
                "linked": True,
                "plex_username": link.plex_username,
                "discord_id": str(link.discord_id),
                "playlists": [asdict(p) for p in playlists],
            })
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Impossibile caricare le playlist da Plex."}, status=400)

    async def playlist_tracks_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request)
            playlist_id = request.query.get("playlist_id", "").strip()
            raw_uid = request.query.get("discord_id", "").strip()
            link = self._resolve_user_link(guild, channel, raw_uid)
            if not link:
                raise PlexError("Collega prima il tuo account Plex per accedere alle tue playlist.")
            settings = self.bot.store.get(guild.id)
            tracks = await self.bot.plex.playlist_tracks(settings, playlist_id, user_token=link.plex_token)
            return web.json_response({"tracks": [asdict(t) for t in tracks]})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Impossibile caricare i brani della playlist."}, status=400)

    async def search_handler(self, request: web.Request):
        try:
            guild, _ = self.resolve_context(request)
            query = request.query.get("query", "").strip()
            library = request.query.get("library", "").strip() or None
            if not query or len(query) > 200:
                raise PlexError("Inserisci un titolo o autore da 1 a 200 caratteri.")
            settings = self.bot.store.get(guild.id)
            tracks = await self.bot.plex.search(settings, query, library)
            return web.json_response({"tracks": [asdict(t) for t in tracks[:50]]})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)

    async def control_handler(self, request: web.Request):
        try:
            data = await request.json()
            action = data.get("action", "")
            guild, channel = self.resolve_context(request, require_active=(action != "volume"))
            settings = self.bot.store.get(guild.id)
            if settings.dj_only:
                raw_uid = str(data.get("user_id") or request.query.get("user_id") or "").strip()
                member = guild.get_member(int(raw_uid)) if raw_uid.isdigit() and hasattr(guild, "get_member") else None
                if not member and raw_uid.isdigit() and hasattr(guild, "fetch_member"):
                    with contextlib.suppress(Exception):
                        member = await guild.fetch_member(int(raw_uid))
                if not member or not self.bot.can_control(guild, member, settings):
                    dj_role_obj = guild.get_role(settings.dj_role) if settings.dj_role and hasattr(guild, "get_role") else None
                    role_hint = f" o il ruolo @{dj_role_obj.name}" if dj_role_obj else ""
                    raise PlexError(f"I controlli della musica sono riservati: serve il permesso Gestisci Server{role_hint}.")
            message = ""
            async with self.bot.config_lock(guild.id):
                player = self.bot.player(guild)
                voice = guild.voice_client
                if action == "play":
                    raw = data.get("track") or {}
                    track_id = str(raw.get("id", ""))
                    if not track_id.isdigit():
                        raise PlexError("Brano non valido.")
                    play_now = bool(data.get("play_now"))
                    track = Track(
                        track_id,
                        str(raw.get("title") or "Senza titolo")[:200],
                        str(raw.get("artist") or "Artista sconosciuto")[:200],
                        str(raw.get("album") or "")[:200],
                        str(raw.get("library") or "Musica")[:100],
                        int(raw.get("duration") or 0),
                    )
                    await player.add(channel, track, player.text_channel, play_now=play_now)
                    message = f"{'▶️ In riproduzione' if play_now else '➕ Aggiunto in coda'}: {track.label}"
                elif action == "play_playlist":
                    playlist_id = str(data.get("playlist_id") or "").strip()
                    raw_uid = str(data.get("discord_id") or "").strip()
                    play_now = bool(data.get("play_now"))
                    shuffle = bool(data.get("shuffle"))
                    link = self._resolve_user_link(guild, channel, raw_uid)
                    if not link:
                        raise PlexError("Collega prima il tuo account Plex per riprodurre le tue playlist.")
                    settings = self.bot.store.get(guild.id)
                    tracks = await self.bot.plex.playlist_tracks(settings, playlist_id, user_token=link.plex_token)
                    added = await player.add_many(
                        channel, tracks, player.text_channel,
                        play_now=play_now, shuffle_tracks=shuffle,
                    )
                    mode_lbl = "🔀 In riproduzione (shuffle)" if (play_now and shuffle) else ("▶️ In riproduzione" if play_now else "➕ Aggiunti in coda")
                    message = f"{mode_lbl}: {added} brani dalla playlist!"
                elif action == "volume":
                    vol = max(0, min(150, int(data.get("volume", 100))))
                    settings = self.bot.store.get(guild.id)
                    settings.volume = vol
                    self.bot.store.save(guild.id, settings)
                    player.set_volume(vol)
                    message = f"🔊 Volume impostato al {vol}%."
                else:
                    if not voice:
                        raise PlexError("Il bot non è connesso a un canale vocale.")
                    if action == "toggle":
                        if voice.is_paused():
                            player.resume()
                            message = "▶️ Riproduzione ripresa."
                        else:
                            player.pause()
                            message = "⏸️ In pausa."
                    elif action == "skip":
                        player.skip()
                        message = "⏭️ Brano saltato."
                    elif action == "seek":
                        player.seek(int(data.get("seconds", 0)))
                        message = "⏩ Posizione aggiornata."
                    elif action == "shuffle":
                        player.shuffle()
                        message = "🔀 Coda mescolata."
                    elif action == "remove":
                        removed = player.remove(int(data.get("index", -1)))
                        message = f"Rimosso: {removed.label}"
                    elif action == "promote":
                        play_now = bool(data.get("play_now"))
                        promoted = player.promote(int(data.get("index", -1)), play_now=play_now)
                        message = f"{'▶️ In riproduzione' if play_now else '⬆️ Spostato in cima'}: {promoted.label}"
                    elif action == "stop":
                        player.stop()
                        message = "⏹️ Riproduzione fermata e coda svuotata."
                    elif action == "leave":
                        await player.close()
                        message = "👋 Disconnesso dal canale vocale."
                    else:
                        raise PlexError("Azione non supportata.")
            return web.json_response({"message": message, "state": await self.build_state(guild, channel)})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Richiesta non valida."}, status=400)

    async def config_handler(self, request: web.Request):
        try:
            guild, channel = self.resolve_context(request, require_active=False)
            data = await request.json()
            action = data.get("action", "")
            message = ""
            extra = {}
            async with self.bot.config_lock(guild.id):
                settings = self.bot.store.get(guild.id)
                admin_actions = {
                    "set_mode", "save_discord_secret", "plex_pin", "plex_check_pin",
                    "plex_logout", "plex_server", "plex_address", "plex_all_libraries",
                    "plex_library", "save_settings",
                }
                if action in admin_actions and settings.dj_only:
                    raw_uid = str(data.get("user_id") or request.query.get("user_id") or "").strip()
                    if raw_uid.isdigit():
                        member = guild.get_member(int(raw_uid)) if hasattr(guild, "get_member") else None
                        if not member and hasattr(guild, "fetch_member"):
                            with contextlib.suppress(Exception):
                                member = await guild.fetch_member(int(raw_uid))
                        if member and not self.bot.can_control(guild, member, settings):
                            raise PlexError("Solo gli amministratori (o utenti autorizzati) possono modificare la configurazione.")
                if action == "set_mode":
                    mode = str(data.get("mode", "commands"))
                    if mode not in ("commands", "activity"):
                        raise PlexError("Modalità non valida.")
                    settings.mode = mode
                    self.bot.store.save(guild.id, settings)
                    message = f"Modalità impostata su: {'🎛️ Activity' if mode == 'activity' else '💬 Comandi Slash'}."
                elif action == "save_discord_secret":
                    sec = str(data.get("client_secret") or "").strip()
                    if not sec:
                        raise PlexError("Inserisci un Client Secret valido.")
                    if hasattr(self.bot.store, "set_meta"):
                        self.bot.store.set_meta("discord_client_secret", sec)
                    message = "💾 Discord Client Secret salvato! Ora puoi autorizzare l'RPC."
                elif action == "plex_pin":
                    pin_id, code, auth_url, expiry = await self.bot.plex.pin_code()
                    self.pending_pins[guild.id] = pin_id
                    extra["code"] = code
                    extra["auth_url"] = auth_url
                    extra["expiry"] = expiry
                    message = f"Inserisci il codice {code} su plex.tv/link"
                elif action == "plex_check_pin":
                    pin = self.pending_pins.get(guild.id)
                    if not pin:
                        raise PlexError("Avvia prima 'Collega con PIN a 4 Cifre'.")
                    token = await self.bot.plex.check_pin(pin)
                    if not token:
                        raise PlexError("Codice PIN non ancora autorizzato su plex.tv/link.")
                    await self.bot.disconnect(guild.id)
                    settings.token = token
                    settings.server_token = settings.server_id = settings.server_name = settings.server_url = ""
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.pending_pins.pop(guild.id, None)
                    extra["ok"] = True
                    message = "✅ Login Plex completato! Ora carica e scegli il tuo server Plex."
                elif action == "user_pin":
                    raw_uid = str(data.get("discord_id", "")).strip()
                    if not raw_uid.isdigit():
                        raise PlexError("Seleziona prima il tuo utente Discord.")
                    uid = int(raw_uid)
                    cid = f"{self.bot.store.client_id}-u{uid}"
                    pin_id, code, auth_url, expiry = await self.bot.plex.pin_code(client_id=cid)
                    self.pending_user_pins[uid] = (pin_id, cid)
                    extra["code"] = code
                    extra["auth_url"] = auth_url
                    extra["expiry"] = expiry
                    message = f"Inserisci il codice {code} su plex.tv/link"
                elif action == "user_check_pin":
                    raw_uid = str(data.get("discord_id", "")).strip()
                    if not raw_uid.isdigit():
                        raise PlexError("Seleziona prima il tuo utente Discord.")
                    uid = int(raw_uid)
                    pending = self.pending_user_pins.get(uid)
                    if not pending:
                        raise PlexError("Genera prima il codice PIN a 4 cifre.")
                    pin_id, cid = pending
                    user_token = await self.bot.plex.check_pin(pin_id, client_id=cid)
                    if not user_token:
                        raise PlexError("Codice PIN non ancora autorizzato su plex.tv/link.")
                    plex_user = await self.bot.plex.user_info(user_token)
                    d_name = self.user_name_cache.get(uid, f"Utente {uid}")
                    self.bot.store.save_user(UserLink(discord_id=uid, plex_token=user_token, plex_username=plex_user, discord_name=d_name))
                    self.pending_user_pins.pop(uid, None)
                    extra["ok"] = True
                    player = self.bot.players.get(guild.id)
                    if player and player.current:
                        asyncio.create_task(player.sync_timeline("paused" if player.paused_at else "playing", player.current))
                    message = f"🎧 Account Plex '{plex_user}' collegato a {d_name}!"
                elif action == "user_unlink":
                    raw_uid = str(data.get("discord_id", "")).strip()
                    if not raw_uid.isdigit():
                        raise PlexError("Utente non valido.")
                    uid = int(raw_uid)
                    self.bot.store.delete_user(uid)
                    self.pending_user_pins.pop(uid, None)
                    message = "🗑️ Account Plex scollegato dal profilo Discord."
                elif action == "plex_logout":
                    await self.bot.disconnect(guild.id)
                    settings.token = settings.server_token = settings.server_id = settings.server_name = settings.server_url = ""
                    settings.address_override = ""
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = "🚪 Credenziali del server Plex rimosse."
                elif action == "plex_servers":
                    if not settings.token:
                        raise PlexError("Collega prima l'account Plex.")
                    resources = await self.bot.plex.resources(settings.token)
                    extra["servers"] = [
                        {
                            "id": r["clientIdentifier"],
                            "name": r["name"],
                            "selected": r["clientIdentifier"] == settings.server_id,
                        }
                        for r in resources
                    ]
                    message = f"Trovati {len(extra['servers'])} server Plex."
                elif action == "plex_address":
                    url = str(data.get("url") or "").strip()
                    if url:
                        url = valid_url(url)
                        if settings.server_id and settings.token:
                            resources = await self.bot.plex.resources(settings.token)
                            resource = next((r for r in resources if r["clientIdentifier"] == settings.server_id), None)
                            if not resource:
                                raise PlexError("Server selezionato non trovato.")
                            await self.bot.plex.connect(resource, url)
                            settings.server_url = url
                    await self.bot.disconnect(guild.id)
                    settings.address_override = url
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = f"Indirizzo manuale: {url}" if url else "Indirizzo manuale rimosso (rilevamento automatico)."
                elif action == "plex_server":
                    server_id = str(data.get("server_id") or "").strip()
                    if not settings.token:
                        raise PlexError("Collega prima l'account Plex.")
                    resources = await self.bot.plex.resources(settings.token)
                    resource = next((r for r in resources if r["clientIdentifier"] == server_id), None)
                    if not resource:
                        raise PlexError("Server Plex non trovato.")
                    url, srv_token = await self.bot.plex.connect(resource, settings.address_override)
                    await self.bot.disconnect(guild.id)
                    settings.server_id, settings.server_name = server_id, resource["name"]
                    settings.server_url, settings.server_token = url, srv_token
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = f"✅ Connesso al server Plex: {settings.server_name}"
                elif action == "plex_all_libraries":
                    await self.bot.disconnect(guild.id)
                    settings.libraries = None
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = "✅ Tutte le librerie musicali sono abilitate."
                elif action == "plex_library":
                    lib_id = str(data.get("library_id") or "").strip()
                    enabled = bool(data.get("enabled"))
                    libs = await self.bot.plex.libraries(settings)
                    known = {lib.id for lib in libs}
                    if lib_id not in known:
                        raise PlexError("Libreria musicale non trovata.")
                    await self.bot.disconnect(guild.id)
                    active = set(known if settings.libraries is None else settings.libraries) & known
                    if enabled:
                        active.add(lib_id)
                    else:
                        active.discard(lib_id)
                    settings.libraries = sorted(active)
                    self.bot.store.save(guild.id, settings)
                    self.lib_cache.pop(guild.id, None)
                    message = f"Libreria {lib_id}: {'abilitata' if enabled else 'disabilitata'}."
                elif action == "save_settings":
                    settings.volume = max(0, min(150, int(data.get("volume", settings.volume))))
                    settings.bitrate = max(32, min(320, int(data.get("bitrate", settings.bitrate))))
                    settings.idle_seconds = max(15, min(1800, int(data.get("idle_seconds", settings.idle_seconds))))
                    settings.max_queue = max(1, min(500, int(data.get("max_queue", settings.max_queue))))
                    if "dj_only" in data:
                        settings.dj_only = bool(data.get("dj_only"))
                    if "dj_role" in data:
                        raw_role = str(data.get("dj_role") or "").strip()
                        settings.dj_role = int(raw_role) if raw_role.isdigit() else None
                    if "language" in data:
                        lang = str(data.get("language") or "en").strip().lower()
                        if lang in ("en", "it"):
                            settings.language = lang
                    self.bot.store.save(guild.id, settings)
                    player = self.bot.players.get(guild.id)
                    if player:
                        player.set_volume(settings.volume)
                    message = "💾 Impostazioni salvate."
                else:
                    raise PlexError("Azione di configurazione non supportata.")
            return web.json_response({"message": message, "state": await self.build_state(guild, channel), **extra})
        except PlexError as error:
            return web.json_response({"error": str(error)}, status=400)
        except Exception:
            return web.json_response({"error": "Richiesta di configurazione non valida."}, status=400)

    async def art_handler(self, request: web.Request):
        try:
            guild, _ = self.resolve_context(request)
            track_id = request.match_info.get("track_id", "")
            is_playlist = track_id.startswith("pl_") and track_id[3:].isdigit()
            if not track_id.isdigit() and not is_playlist:
                return web.Response(status=404)
            key = (guild.id, track_id)
            if key not in self.art_cache:
                settings = self.bot.store.get(guild.id)
                art = await self.bot.plex.artwork(settings, track_id)
                if not art:
                    return web.Response(status=404)
                self.art_cache[key] = art
                if len(self.art_cache) > 120:
                    self.art_cache.pop(next(iter(self.art_cache)))
            body, content_type = self.art_cache[key]
            return web.Response(body=body, content_type=content_type, headers={"Cache-Control": "private, max-age=3600"})
        except Exception:
            return web.Response(status=404)

    async def cover_handler(self, request: web.Request):
        """Copertina pubblica firmata per singolo brano, usata solo dal Rich Presence Discord."""
        try:
            presence = getattr(self.bot, "presence", None)
            raw_guild = request.match_info.get("guild_id", "")
            track_id = request.match_info.get("track_id", "")
            sig = request.match_info.get("sig", "").removesuffix(".jpg")
            if presence is None or not raw_guild.isdigit() or not track_id.isdigit():
                return web.Response(status=404)
            guild_id = int(raw_guild)
            if not hmac.compare_digest(presence.cover_sig(guild_id, track_id), sig):
                return web.Response(status=404)
            if not self.bot.get_guild(guild_id):
                return web.Response(status=404)
            key = (guild_id, track_id)
            if key not in self.art_cache:
                art = await self.bot.plex.artwork(self.bot.store.get(guild_id), track_id)
                if not art:
                    return web.Response(status=404)
                self.art_cache[key] = art
                if len(self.art_cache) > 120:
                    self.art_cache.pop(next(iter(self.art_cache)))
            body, content_type = self.art_cache[key]
            return web.Response(body=body, content_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            return web.Response(status=404)

    async def ws_handler(self, request: web.Request):
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(request)
        try:
            while not ws.closed:
                with contextlib.suppress(PlexError):
                    guild, channel = self.resolve_context(request)
                    state = await self.build_state(guild, channel)
                    await ws.send_str(json.dumps(state))
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                    if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
                except TimeoutError:
                    pass
        except Exception:
            pass
        finally:
            with contextlib.suppress(Exception):
                await ws.close()
        return ws

    def create_app(self) -> web.Application:
        app = web.Application(client_max_size=65536)
        app.router.add_get("/", self.index)
        app.router.add_get("/api/logo", self.logo_handler)
        app.router.add_get("/api/banner", self.banner_handler)
        app.router.add_get("/api/state", self.state_handler)
        app.router.add_get("/api/search", self.search_handler)
        app.router.add_get("/api/playlists", self.playlists_handler)
        app.router.add_get("/api/playlist_tracks", self.playlist_tracks_handler)
        app.router.add_post("/api/control", self.control_handler)
        app.router.add_post("/api/config", self.config_handler)
        app.router.add_post("/api/discord_token", self.discord_token_handler)
        app.router.add_get("/api/art/{guild_id}/{track_id}", self.art_handler)
        app.router.add_get("/api/cover/{guild_id}/{track_id}/{sig}", self.cover_handler)
        app.router.add_get("/api/ws", self.ws_handler)
        return app

    async def start(self):
        if self.port <= 0:
            return
        app = self.create_app()
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()

    async def close(self):
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
