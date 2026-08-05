from __future__ import annotations

import atexit
import json
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from app.data.database.database import DB
from app.data.resources.resources import RESOURCES
from app.engine.game_state import game
from app.engine.runtime_debugger import RuntimeDebugger
from app.engine.runtime_debugger_controller import get_controller
from app.events import event_commands, event_validators
from app.events.event_structs import ParseMode
from app.events.event_version import EventVersion
from app.events.triggers import GenericTrigger


DEBUGGER_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Lex Talionis Runtime Debugger</title>
<style>
:root { color-scheme: dark; --bg:#11151c; --panel:#1b2330; --line:#334155; --accent:#60a5fa; --good:#4ade80; --bad:#fb7185; --text:#e5edf7; --muted:#94a3b8; }
* { box-sizing:border-box; }
body { margin:0; height:100vh; overflow:hidden; background:var(--bg); color:var(--text); font:14px/1.35 "Segoe UI",sans-serif; }
header { height:58px; display:flex; align-items:center; gap:18px; padding:0 18px; background:#0b1017; border-bottom:1px solid var(--line); }
header h1 { font-size:18px; margin:0; }
#connection { color:var(--muted); }
.connected { color:var(--good)!important; } .disconnected { color:var(--bad)!important; }
.layout { display:grid; grid-template-columns:290px 1fr; height:calc(100vh - 58px); }
aside { border-right:1px solid var(--line); padding:12px; overflow:hidden; display:flex; flex-direction:column; gap:10px; }
input, select, textarea, button { font:inherit; color:var(--text); background:#111827; border:1px solid var(--line); border-radius:6px; }
input, select, textarea { padding:7px 9px; }
button { padding:7px 11px; cursor:pointer; }
button:hover { border-color:var(--accent); background:#17243a; }
button.primary { background:#1d4ed8; border-color:#3b82f6; }
button.danger { border-color:#9f1239; }
#unitFilter { width:100%; }
#unitList { overflow:auto; display:flex; flex-direction:column; gap:4px; padding-right:3px; }
.unit { text-align:left; display:grid; grid-template-columns:1fr auto; gap:3px 8px; }
.unit small { color:var(--muted); grid-column:1 / -1; }
.unit.selected { border-color:var(--accent); background:#17243a; }
.item-picker { display:grid; grid-template-columns:minmax(180px,1fr) 72px 20px auto; gap:8px; align-items:center; width:100%; }
.item-icon { width:18px; height:18px; border:1px solid var(--line); border-radius:3px; background-color:#0b1017; background-repeat:no-repeat; image-rendering:pixelated; }
.item-icon.empty { background-image:none!important; }
.hotkey { color:#fbbf24; font-size:12px; white-space:nowrap; }
.check { display:flex; align-items:center; gap:6px; white-space:nowrap; color:#cbd5e1; }
.check input { width:16px; height:16px; margin:0; accent-color:#3b82f6; }
main { overflow:auto; padding:14px; }
.grid { display:grid; grid-template-columns:repeat(2,minmax(310px,1fr)); gap:12px; align-items:start; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:13px; }
.card h2 { font-size:15px; margin:0 0 10px; color:#bfdbfe; }
.row { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:7px 0; }
.row > input, .row > select, .row > textarea { flex:1; min-width:0; }
.buttons { display:flex; flex-wrap:wrap; gap:7px; }
#fields { display:grid; grid-template-columns:minmax(130px,1fr) 100px 58px; gap:5px 8px; align-items:center; max-height:430px; overflow:auto; padding-right:3px; }
#fields label { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
#fields input { width:100%; }
#commandBrowser { margin-top:10px; border-top:1px solid var(--line); padding-top:10px; }
#commandTools { display:grid; grid-template-columns:1fr 220px; gap:8px; margin-bottom:8px; }
#commandLayout { display:grid; grid-template-columns:minmax(240px,330px) minmax(0,1fr); gap:10px; min-height:300px; }
#commandList { max-height:360px; overflow:auto; display:flex; flex-direction:column; gap:3px; }
.command-entry { text-align:left; }
.command-entry strong { color:#bfdbfe; }
.command-entry small { display:block; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.command-entry.selected { border-color:var(--accent); background:#17243a; }
#commandDetail { min-width:0; background:#111827; border:1px solid var(--line); border-radius:7px; padding:11px; overflow:auto; }
#commandSignature { color:#93c5fd; font-family:Consolas,monospace; white-space:pre-wrap; word-break:break-word; }
#commandDescription { white-space:pre-wrap; color:#cbd5e1; }
#commandFlags { color:#fbbf24; }
#commandArguments { margin:8px 0; display:grid; gap:6px; }
.command-argument { border-left:2px solid var(--line); padding-left:8px; }
.command-argument strong { color:#bfdbfe; }
.command-argument small { display:block; color:var(--muted); white-space:pre-wrap; }
.event-command-input { position:relative; flex:1; min-width:0; }
.event-command-input textarea { display:block; width:100%; }
#eventSuggestions { position:absolute; z-index:40; top:calc(100% + 4px); left:0; right:0; max-height:260px; overflow:auto; padding:4px; background:#090f18; border:1px solid var(--accent); border-radius:7px; box-shadow:0 12px 28px #000a; }
.event-suggestion { width:100%; display:grid; grid-template-columns:minmax(0,1fr) auto; gap:4px 10px; padding:7px 9px; border:0; border-radius:4px; text-align:left; background:transparent; }
.event-suggestion:hover, .event-suggestion.selected { background:#172b49; }
.event-suggestion strong { color:#dbeafe; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-family:Consolas,monospace; }
.event-suggestion small { color:var(--muted); white-space:nowrap; }
.event-suggestion.flag strong { color:#fbbf24; }
.event-suggestion.generic strong { color:#cbd5e1; font-weight:400; }
#unitTitle { margin:0 0 4px; font-size:20px; }
#unitMeta { color:var(--muted); margin-bottom:12px; }
#message { position:fixed; right:18px; bottom:16px; max-width:520px; padding:10px 13px; border-radius:7px; background:#07111f; border:1px solid var(--line); color:var(--muted); }
#message.ok { color:var(--good); } #message.error { color:var(--bad); }
.wide { grid-column:1 / -1; }
textarea { resize:vertical; min-height:76px; }
@media (max-width:900px) { .layout { grid-template-columns:230px 1fr; } .grid { grid-template-columns:1fr; } }
@media (max-width:720px) { #commandTools, #commandLayout { grid-template-columns:1fr; } }
</style>
</head>
<body>
<header>
  <h1>Lex Talionis Runtime Debugger</h1>
  <span id="connection">Connecting...</span>
  <span id="level"></span>
  <span id="turn"></span>
  <span id="money"></span>
</header>
<div class="layout">
  <aside>
    <input id="unitFilter" placeholder="Filter units...">
    <div id="unitList"></div>
  </aside>
  <main>
    <h2 id="unitTitle">Select a unit</h2>
    <div id="unitMeta">The game keeps running while this window is open.</div>
    <div class="grid">
      <section class="card">
        <h2>Selected unit values</h2>
        <div id="fields"></div>
      </section>
      <section class="card">
        <h2>Selected unit actions</h2>
        <div class="buttons">
          <button id="maxUnit">Max selected unit <span class="hotkey">(Ctrl+1)</span></button>
          <button id="autoLevelUnit">Auto level +1</button>
        </div>
        <div class="row item-picker">
          <select id="itemSelect"></select>
          <input id="itemUses" type="number" min="0" placeholder="Uses" title="Number of uses on the received item">
          <span id="itemIcon" class="item-icon empty" title="Selected item icon"></span>
          <button id="giveItem">Give item</button>
        </div>
        <div class="row">
          <input id="teleportX" type="number" placeholder="X">
          <input id="teleportY" type="number" placeholder="Y">
          <button id="pickPosition">Pick from game</button>
          <button id="teleport">Teleport</button>
        </div>
      </section>
      <section class="card">
        <h2>Batch unit actions</h2>
        <div class="buttons">
          <button data-op="max_players">Max all player units <span class="hotkey">(Ctrl+2)</span></button>
          <button data-op="max_enemies">Max all enemy units <span class="hotkey">(Ctrl+3)</span></button>
          <button data-op="enemy_hp">Set enemy HP to 1 <span class="hotkey">(Ctrl+4)</span></button>
          <button data-op="enemy_ai">Set enemy AI to None <span class="hotkey">(Ctrl+5)</span></button>
        </div>
      </section>
      <section class="card">
        <h2>Chapter and party</h2>
        <div class="buttons">
          <button class="danger" data-op="complete_chapter">Complete current chapter <span class="hotkey">(Ctrl+0)</span></button>
          <button id="restartChapter">Restart current chapter</button>
        </div>
        <div class="row">
          <select id="chapterSelect"></select>
          <select id="chapterDifficulty"></select>
          <button id="goChapter">Go to chapter</button>
        </div>
        <div class="row">
          <input id="moneyInput" type="number" min="0" placeholder="Money">
          <button id="setMoney">Set money</button>
        </div>
        <div class="row">
          <input id="turnInput" type="number" min="0" placeholder="Turn count">
          <button id="setTurn">Change turn count</button>
        </div>
        <div class="row">
          <input id="turnwheelUses" type="number" min="-1" placeholder="Turnwheel uses" title="-1 means unlimited uses">
          <label class="check">
            <input id="turnwheelEnabled" type="checkbox">
            Enable turnwheel
          </label>
          <button id="setTurnwheel">Set turnwheel</button>
        </div>
        <div class="row">
          <select id="weatherSelect"></select>
          <button id="setWeather">Change weather</button>
        </div>
      </section>
      <section class="card wide">
        <h2>Event command console</h2>
        <div class="row">
          <div class="event-command-input">
            <textarea id="eventCommand" spellcheck="false" autocomplete="off" placeholder="Example: give_item;Eirika;Vulnerary"></textarea>
            <div id="eventSuggestions" hidden></div>
          </div>
          <button id="runEvent" class="primary">Run</button>
        </div>
        <button id="showCommands">Show commands</button>
        <div id="commandBrowser" hidden>
          <div id="commandTools">
            <input id="commandSearch" placeholder="Search command, argument, or description...">
            <select id="commandCategory"></select>
          </div>
          <div id="commandLayout">
            <div id="commandList"></div>
            <div id="commandDetail">
              <h2 id="commandName">Select a command</h2>
              <div id="commandSignature"></div>
              <p id="commandFlags"></p>
              <div id="commandArguments"></div>
              <div id="commandDescription"></div>
              <p><button id="insertCommand">Insert template</button></p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </main>
</div>
<div id="message">Waiting for game state...</div>
<script>
const token = new URLSearchParams(location.search).get("token") || "";
let state = {units:[], items:[], chapters:[]};
let selectedNid = null;
let selectedDetail = null;
let lastCatalogSignature = "";
let lastInspectTime = 0;
let lastHeartbeat = -1;
let lastHeartbeatTime = 0;
let lastPickRevision = 0;
let lastNotificationRevision = 0;
let selectedCommand = null;
let destinationChosen = false;
let selectionSyncPaused = false;
let pickerWasActive = false;
let pickStartedRevision = 0;
let pickRequestPending = false;
let eventSuggestions = [];
let eventSuggestionIndex = 0;
let eventSuggestionReplaceLength = 0;
let eventSuggestionRequest = 0;
let eventSuggestionTimer = null;
const $ = id => document.getElementById(id);
const message = (text, ok=true) => {
  const el = $("message"); el.textContent = text; el.className = ok ? "ok" : "error";
};
async function apiState() {
  const response = await fetch(`/api/state?token=${encodeURIComponent(token)}`, {cache:"no-store"});
  if (!response.ok) throw new Error(`State request failed (${response.status})`);
  return response.json();
}
async function command(op, args={}) {
  const response = await fetch(`/api/command?token=${encodeURIComponent(token)}`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({op,args})
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.message || `Command failed (${response.status})`);
  if (result.message) message(result.message, true);
  return result;
}
function hideEventSuggestions() {
  clearTimeout(eventSuggestionTimer);
  eventSuggestionTimer = null;
  eventSuggestionRequest += 1;
  eventSuggestions = [];
  eventSuggestionIndex = 0;
  $("eventSuggestions").hidden = true;
  $("eventSuggestions").replaceChildren();
}
function renderEventSuggestions() {
  const popup = $("eventSuggestions");
  popup.replaceChildren();
  if (!eventSuggestions.length) {
    popup.hidden = true;
    return;
  }
  eventSuggestions.forEach((suggestion, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `event-suggestion ${suggestion.kind || "normal"}` +
      (index === eventSuggestionIndex ? " selected" : "");
    const name = document.createElement("strong");
    name.textContent = suggestion.display;
    const context = document.createElement("small");
    context.textContent = suggestion.context || "";
    button.append(name, context);
    button.onmousedown = mouseEvent => {
      mouseEvent.preventDefault();
      applyEventSuggestion(index);
    };
    popup.append(button);
  });
  popup.hidden = false;
  popup.children[eventSuggestionIndex]?.scrollIntoView({block:"nearest"});
}
function currentEventLine() {
  const editor = $("eventCommand");
  const beforeCursor = editor.value.slice(0, editor.selectionStart);
  return beforeCursor.slice(beforeCursor.lastIndexOf("\n") + 1);
}
async function requestEventSuggestions() {
  const editor = $("eventCommand");
  if (document.activeElement !== editor) return hideEventSuggestions();
  const requestId = ++eventSuggestionRequest;
  try {
    const result = await command("event_suggestions", {
      line:currentEventLine(),
      source:editor.value
    });
    if (requestId !== eventSuggestionRequest || document.activeElement !== editor) return;
    eventSuggestions = result.suggestions || [];
    eventSuggestionReplaceLength = Number(result.replace_length || 0);
    eventSuggestionIndex = 0;
    renderEventSuggestions();
  } catch (_error) {
    if (requestId === eventSuggestionRequest) hideEventSuggestions();
  }
}
function scheduleEventSuggestions(immediate=false) {
  clearTimeout(eventSuggestionTimer);
  if (immediate) requestEventSuggestions();
  else eventSuggestionTimer = setTimeout(requestEventSuggestions, 90);
}
function applyEventSuggestion(index=eventSuggestionIndex) {
  const suggestion = eventSuggestions[index];
  if (!suggestion) return;
  const editor = $("eventCommand");
  const end = editor.selectionStart;
  const start = Math.max(0, end - eventSuggestionReplaceLength);
  editor.setRangeText(suggestion.value, start, end, "end");
  editor.focus();
  hideEventSuggestions();
  if (suggestion.value.endsWith("=")) scheduleEventSuggestions(true);
}
function fillSelect(select, values, valueKey, labelFn) {
  const previous = select.value;
  select.replaceChildren();
  for (const value of values || []) {
    const option = document.createElement("option");
    option.value = value[valueKey]; option.textContent = labelFn(value); select.append(option);
  }
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}
function renderCatalogs() {
  const signature = `${state.level || ""}:${state.items?.length || 0}:${state.chapters?.length || 0}:${state.difficulties?.length || 0}:${state.commands?.length || 0}:${state.weathers?.length || 0}`;
  if (signature === lastCatalogSignature) return;
  lastCatalogSignature = signature;
  fillSelect($("itemSelect"), state.items, "nid", item => `${item.nid}: ${item.name}`);
  fillSelect($("chapterSelect"), state.chapters, "nid", chapter => `${chapter.nid}: ${chapter.name}`);
  for (const option of $("chapterSelect").options) option.disabled = option.value === state.level;
  if ($("chapterSelect").selectedOptions[0]?.disabled) {
    $("chapterSelect").value = [...$("chapterSelect").options].find(option => !option.disabled)?.value || "";
  }
  $("goChapter").disabled = ![...$("chapterSelect").options].some(option => !option.disabled);
  fillSelect($("chapterDifficulty"), state.difficulties, "nid", difficulty => `${difficulty.nid}: ${difficulty.name}`);
  if (!$("chapterDifficulty").dataset.initialized) {
    $("chapterDifficulty").value = state.difficulty_nid || "";
    $("chapterDifficulty").dataset.initialized = "true";
  }
  fillSelect($("weatherSelect"), state.weathers, "nid", weather => weather.name);
  const categories = [...new Set((state.commands || []).map(command => command.category))].sort();
  $("commandCategory").replaceChildren();
  const all = document.createElement("option"); all.value = ""; all.textContent = "All categories";
  $("commandCategory").append(all);
  for (const category of categories) {
    const option = document.createElement("option");
    option.value = category; option.textContent = category; $("commandCategory").append(option);
  }
  renderCommands();
  renderSelectedItem();
}
function selectedItemInfo() {
  return (state.items || []).find(item => item.nid === $("itemSelect").value);
}
function renderSelectedItem() {
  const item = selectedItemInfo();
  const icon = $("itemIcon");
  if (item?.icon_nid) {
    icon.classList.remove("empty");
    icon.style.backgroundImage = `url("/api/icon?token=${encodeURIComponent(token)}&sheet=${encodeURIComponent(item.icon_nid)}")`;
    icon.style.backgroundPosition = `${-item.icon_index[0] * 16}px ${-item.icon_index[1] * 16}px`;
    icon.title = `${item.nid}: ${item.name}`;
  } else {
    icon.classList.add("empty");
    icon.style.backgroundImage = "";
    icon.title = "This item has no icon";
  }
  const uses = $("itemUses");
  if (item?.uses == null) {
    uses.value = "";
    uses.disabled = true;
    uses.placeholder = "N/A";
  } else {
    uses.disabled = false;
    uses.value = item.uses;
    uses.placeholder = "Uses";
  }
}
function renderCommands() {
  const list = $("commandList"); list.replaceChildren();
  const search = $("commandSearch").value.trim().toLowerCase();
  const category = $("commandCategory").value;
  const commands = (state.commands || []).filter(command => {
    if (category && command.category !== category) return false;
    const haystack = `${command.nid} ${command.nickname || ""} ${command.signature} ${command.description}`.toLowerCase();
    return !search || haystack.includes(search);
  });
  for (const commandInfo of commands) {
    const button = document.createElement("button");
    button.className = "command-entry" + (selectedCommand?.nid === commandInfo.nid ? " selected" : "");
    const name = document.createElement("strong"); name.textContent = commandInfo.nid;
    const signature = document.createElement("small"); signature.textContent = commandInfo.signature;
    button.append(name, signature);
    button.onclick = () => selectCommand(commandInfo);
    button.ondblclick = () => insertCommandTemplate(commandInfo);
    list.append(button);
  }
}
function selectCommand(commandInfo) {
  selectedCommand = commandInfo;
  $("commandName").textContent = `${commandInfo.nid} — ${commandInfo.category}`;
  $("commandSignature").textContent = commandInfo.signature;
  $("commandFlags").textContent = commandInfo.flags?.length ? `Optional flags: ${commandInfo.flags.join(", ")}` : "";
  const argumentsBox = $("commandArguments"); argumentsBox.replaceChildren();
  for (const argument of commandInfo.arguments || []) {
    const row = document.createElement("div"); row.className = "command-argument";
    const title = document.createElement("strong");
    title.textContent = `${argument.name}: ${argument.type}${argument.optional ? " (optional)" : ""}`;
    const description = document.createElement("small");
    description.textContent = argument.description || "";
    row.append(title, description); argumentsBox.append(row);
  }
  $("commandDescription").textContent = commandInfo.description || "No description.";
  renderCommands();
}
function insertCommandTemplate(commandInfo=selectedCommand) {
  if (!commandInfo) return message("Select a command first.", false);
  $("eventCommand").value = commandInfo.template;
  $("eventCommand").focus();
  scheduleEventSuggestions(true);
  message(`Inserted ${commandInfo.nid}. Replace <required> and [optional] values before running.`, true);
}
function renderUnits(ensureSelectedVisible=false) {
  const list = $("unitList");
  const oldScroll = list.scrollTop;
  let selectedButton = null;
  const filter = $("unitFilter").value.trim().toLowerCase();
  list.replaceChildren();
  const shown = (state.units || []).filter(unit =>
    !filter || `${unit.nid} ${unit.name} ${unit.team}`.toLowerCase().includes(filter));
  for (const unit of shown) {
    const button = document.createElement("button");
    button.className = "unit" + (unit.nid === selectedNid ? " selected" : "");
    if (unit.nid === selectedNid) selectedButton = button;
    const name = document.createElement("span"); name.textContent = unit.name || unit.nid;
    const team = document.createElement("span"); team.textContent = unit.team;
    const meta = document.createElement("small");
    meta.textContent = `NID: ${unit.nid} | Lv ${unit.level} | HP ${unit.hp}/${unit.max_hp} | Pos ${unit.position ?? "off-map"}`;
    button.append(name, team, meta);
    button.onclick = () => selectUnit(unit.nid, true);
    list.append(button);
  }
  list.scrollTop = oldScroll;
  if (ensureSelectedVisible && selectedButton) {
    selectedButton.scrollIntoView({block:"nearest"});
  }
}
function renderDetail() {
  const fields = $("fields"); fields.replaceChildren();
  if (!selectedDetail) {
    $("unitTitle").textContent = "Select a unit";
    $("unitMeta").textContent = "The game keeps running while this window is open.";
    return;
  }
  $("unitTitle").textContent = selectedDetail.name || selectedDetail.nid;
  $("unitMeta").textContent = `NID: ${selectedDetail.nid} | Team: ${selectedDetail.team} | Class: ${selectedDetail.klass} | Items: ${selectedDetail.inventory.join(", ") || "None"}`;
  for (const field of selectedDetail.fields) {
    const label = document.createElement("label"); label.textContent = field.label; label.title = field.label;
    const input = document.createElement("input");
    input.type = "number"; input.value = field.value; input.min = field.minimum; input.max = field.maximum;
    const apply = document.createElement("button"); apply.textContent = "Set";
    const submit = async () => {
      try {
        await command("set_field", {nid:selectedNid, key:field.key, value:Number(input.value)});
        await inspectSelected();
      } catch (error) { message(error.message, false); }
    };
    apply.onclick = submit;
    input.onkeydown = event => { if (event.key === "Enter") submit(); };
    fields.append(label, input, apply);
  }
  const pos = selectedDetail.position;
  if (pos && !destinationChosen) {
    $("teleportX").value = pos[0];
    $("teleportY").value = pos[1];
  }
}
async function selectUnit(nid, focusGame=false) {
  const changed = selectedNid !== nid;
  selectedNid = nid;
  renderUnits(changed);
  if (focusGame) {
    try {
      await command("focus_unit", {nid});
      selectionSyncPaused = false;
    }
    catch (error) { message(error.message, false); }
  }
  if (changed || !selectedDetail) await inspectSelected();
}
async function inspectSelected() {
  if (!selectedNid) { selectedDetail = null; renderDetail(); return; }
  const requestedNid = selectedNid;
  try {
    const result = await command("inspect_unit", {nid:requestedNid});
    if (selectedNid === requestedNid) {
      selectedDetail = result.detail; lastInspectTime = Date.now(); renderDetail();
    }
  } catch (error) {
    if (selectedNid === requestedNid) {
      selectedDetail = null; renderDetail(); message(error.message, false);
    }
  }
}
async function refresh() {
  try {
    state = await apiState();
    if (state.heartbeat !== lastHeartbeat) {
      lastHeartbeat = state.heartbeat;
      lastHeartbeatTime = Date.now();
    }
    const gameSynced = state.runtime_active && Date.now() - lastHeartbeatTime < 2000;
    $("connection").textContent = gameSynced ? "Game synced" : "Waiting for game loop...";
    $("connection").className = gameSynced ? "connected" : "disconnected";
    if (state.runtime_error) message(`Runtime sync error: ${state.runtime_error}`, false);
    $("level").textContent = `Chapter: ${state.level || "none"}`;
    $("turn").textContent = state.turncount == null ? "" : `Turn: ${state.turncount}`;
    $("money").textContent = state.money == null ? "" : `Money: ${state.money}`;
    if (state.money != null && document.activeElement !== $("moneyInput")) {
      $("moneyInput").value = state.money;
    }
    if (state.turncount != null && document.activeElement !== $("turnInput")) {
      $("turnInput").value = state.turncount;
    }
    if (state.turnwheel) {
      if (document.activeElement !== $("turnwheelUses")) {
        $("turnwheelUses").value = state.turnwheel.current_uses;
        $("turnwheelUses").title =
          `Current: ${state.turnwheel.current_uses}; Max: ${state.turnwheel.max_uses}; -1 means unlimited`;
      }
      if (document.activeElement !== $("turnwheelEnabled")) {
        $("turnwheelEnabled").checked = Boolean(state.turnwheel.enabled);
      }
    }
    renderCatalogs();
    if (document.activeElement !== $("weatherSelect")) {
      $("weatherSelect").value = state.weather?.[0] || "";
    }
    if (state.picked_position && state.picked_position.revision > lastPickRevision) {
      lastPickRevision = state.picked_position.revision;
      destinationChosen = true;
      selectionSyncPaused = true;
      $("teleportX").value = state.picked_position.x;
      $("teleportY").value = state.picked_position.y;
      message(`Picked destination X=${state.picked_position.x}, Y=${state.picked_position.y}.`, true);
    }
    if (!pickRequestPending && pickerWasActive && !state.picking_position &&
        (!state.picked_position || state.picked_position.revision <= pickStartedRevision)) {
      selectionSyncPaused = false;
    }
    if (!pickRequestPending) pickerWasActive = Boolean(state.picking_position);
    if (state.notification && state.notification.revision > lastNotificationRevision) {
      lastNotificationRevision = state.notification.revision;
      message(state.notification.message, state.notification.ok);
    }
    if (selectedNid && !(state.units || []).some(unit => unit.nid === selectedNid)) {
      selectedNid = null; selectedDetail = null; renderDetail();
    }
    const hoveredNid = state.hovered_unit_nid;
    if (!selectionSyncPaused && hoveredNid && hoveredNid !== selectedNid) {
      selectUnit(hoveredNid, false);
    } else if (!selectedNid && state.units?.length) {
      selectUnit(state.units[0].nid, false);
    }
    renderUnits();
    const activeTag = document.activeElement?.tagName;
    const editing = activeTag === "INPUT" || activeTag === "SELECT" || activeTag === "TEXTAREA";
    if (selectedNid && !editing && Date.now() - lastInspectTime > 1000) inspectSelected();
  } catch (error) {
    $("connection").textContent = "Disconnected";
    $("connection").className = "disconnected";
    message(error.message, false);
  }
}
$("unitFilter").oninput = renderUnits;
$("itemSelect").onchange = renderSelectedItem;
$("teleportX").oninput = () => { destinationChosen = true; };
$("teleportY").oninput = () => { destinationChosen = true; };
$("maxUnit").onclick = async () => {
  if (!selectedNid) return message("Select a unit first.", false);
  try { await command("max_unit", {nid:selectedNid}); await inspectSelected(); } catch (e) { message(e.message, false); }
};
$("autoLevelUnit").onclick = async () => {
  if (!selectedNid) return message("Select a unit first.", false);
  try { await command("auto_level_unit", {nid:selectedNid}); await inspectSelected(); } catch (e) { message(e.message, false); }
};
$("giveItem").onclick = async () => {
  if (!selectedNid) return message("Select a unit first.", false);
  const usesInput = $("itemUses");
  const args = {nid:selectedNid,item_nid:$("itemSelect").value};
  if (!usesInput.disabled && usesInput.value !== "") args.uses = Number(usesInput.value);
  try { await command("give_item", args); await inspectSelected(); } catch (e) { message(e.message, false); }
};
$("teleport").onclick = async () => {
  if (!selectedNid) return message("Select a unit first.", false);
  try {
    await command("teleport", {nid:selectedNid,x:Number($("teleportX").value),y:Number($("teleportY").value)});
    destinationChosen = false;
    selectionSyncPaused = false;
    await inspectSelected();
  } catch (e) { message(e.message, false); }
};
$("pickPosition").onclick = async () => {
  selectionSyncPaused = true;
  pickerWasActive = true;
  pickStartedRevision = lastPickRevision;
  pickRequestPending = true;
  try { await command("begin_pick_position"); }
  catch (e) {
    selectionSyncPaused = false;
    message(e.message, false);
  }
  finally { pickRequestPending = false; }
};
document.querySelectorAll("[data-op]").forEach(button => button.onclick = async () => {
  try { await command(button.dataset.op); await refresh(); if (selectedNid) await inspectSelected(); } catch (e) { message(e.message, false); }
});
$("goChapter").onclick = async () => {
  try { await command("go_chapter", {level_nid:$("chapterSelect").value, difficulty_nid:$("chapterDifficulty").value}); } catch (e) { message(e.message, false); }
};
$("restartChapter").onclick = async () => {
  try { await command("restart_chapter", {difficulty_nid:$("chapterDifficulty").value}); await refresh(); } catch (e) { message(e.message, false); }
};
$("setMoney").onclick = async () => {
  try { await command("set_money", {value:Number($("moneyInput").value)}); await refresh(); } catch (e) { message(e.message, false); }
};
$("setTurn").onclick = async () => {
  try { await command("set_turn_count", {value:Number($("turnInput").value)}); await refresh(); } catch (e) { message(e.message, false); }
};
$("setTurnwheel").onclick = async () => {
  try {
    await command("set_turnwheel", {
      uses:Number($("turnwheelUses").value),
      enabled:$("turnwheelEnabled").checked
    });
    await refresh();
  } catch (e) { message(e.message, false); }
};
$("setWeather").onclick = async () => {
  try { await command("set_weather", {weather_nid:$("weatherSelect").value}); await refresh(); } catch (e) { message(e.message, false); }
};
$("eventCommand").oninput = () => scheduleEventSuggestions();
$("eventCommand").onfocus = () => scheduleEventSuggestions(true);
$("eventCommand").onclick = () => scheduleEventSuggestions(true);
$("eventCommand").onblur = () => setTimeout(() => {
  if (document.activeElement !== $("eventCommand")) hideEventSuggestions();
}, 120);
$("eventCommand").onkeydown = keyEvent => {
  const popupOpen = !$("eventSuggestions").hidden && eventSuggestions.length;
  if (popupOpen && keyEvent.key === "ArrowDown") {
    keyEvent.preventDefault();
    eventSuggestionIndex = (eventSuggestionIndex + 1) % eventSuggestions.length;
    renderEventSuggestions();
  } else if (popupOpen && keyEvent.key === "ArrowUp") {
    keyEvent.preventDefault();
    eventSuggestionIndex =
      (eventSuggestionIndex - 1 + eventSuggestions.length) % eventSuggestions.length;
    renderEventSuggestions();
  } else if (popupOpen && (keyEvent.key === "Tab" || keyEvent.key === "Enter")) {
    keyEvent.preventDefault();
    applyEventSuggestion();
  } else if (keyEvent.key === "Escape") {
    hideEventSuggestions();
  } else if (keyEvent.ctrlKey && keyEvent.code === "Space") {
    keyEvent.preventDefault();
    scheduleEventSuggestions(true);
  }
};
$("runEvent").onclick = async () => {
  try { await command("event_command", {script:$("eventCommand").value,nid:selectedNid}); } catch (e) { message(e.message, false); }
};
$("showCommands").onclick = () => {
  const browser = $("commandBrowser");
  browser.hidden = !browser.hidden;
  $("showCommands").textContent = browser.hidden ? "Show commands" : "Hide commands";
  if (!browser.hidden) renderCommands();
};
$("commandSearch").oninput = renderCommands;
$("commandCategory").onchange = renderCommands;
$("insertCommand").onclick = () => insertCommandTemplate();
window.addEventListener("pagehide", () => {
  navigator.sendBeacon(`/api/window-closed?token=${encodeURIComponent(token)}`, "");
});
refresh(); setInterval(refresh, 500);
</script>
</body>
</html>"""


@dataclass
class PendingCommand:
    op: str
    args: Dict[str, Any]
    complete: threading.Event = field(default_factory=threading.Event)
    result: Dict[str, Any] = field(default_factory=dict)


class RuntimeDebuggerService:
    def __init__(self) -> None:
        self._controller = get_controller()
        self._server: Optional[ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._commands: queue.Queue[PendingCommand] = queue.Queue()
        self._snapshot_lock = threading.Lock()
        self._snapshot: Dict[str, Any] = {
            'runtime_active': False, 'heartbeat': 0,
            'level': None, 'turncount': None, 'money': None,
            'units': [], 'items': [], 'chapters': []
        }
        self._catalog: Dict[str, Any] = {'items': [], 'chapters': [], 'weathers': []}
        self._token = secrets.token_urlsafe(24)
        self._url: Optional[str] = None
        self._last_snapshot_time = 0.0
        self._heartbeat = 0
        self._picked_position: Optional[Dict[str, int]] = None
        self._pick_revision = 0
        self._last_client_seen = 0.0
        self._last_window_launch = 0.0
        self._selected_unit_nid: Optional[str] = None
        self._notification: Optional[Dict[str, Any]] = None
        self._notification_revision = 0

    @property
    def url(self) -> Optional[str]:
        return self._url

    def start(self) -> None:
        if self._server:
            self.open_window()
            return
        self._controller.refresh_catalog()
        self._catalog = {
            'items': [{
                'nid': item.nid,
                'name': item.name or item.nid,
                'icon_nid': item.icon_nid,
                'icon_index': list(item.icon_index or (0, 0)),
                'uses': (
                    item.uses.value if item.uses else
                    item.c_uses.value if item.c_uses else None
                ),
            } for item in DB.items],
            'chapters': [{'nid': level.nid, 'name': level.name or level.nid} for level in DB.levels],
            'weathers': (
                [{'nid': '', 'name': 'None (clear weather)'}] +
                [{'nid': weather, 'name': weather} for weather in event_validators.Weather.valid]
            ),
            'commands': self._build_command_catalog(),
        }
        handler = self._make_handler()
        self._server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self._server.daemon_threads = True
        port = self._server.server_address[1]
        self._url = f'http://127.0.0.1:{port}/?token={self._token}'
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name='RuntimeDebuggerHTTP',
            daemon=True)
        self._server_thread.start()
        self.open_window()

    def stop(self, close_window: bool = False) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._server_thread = None
        self._url = None
        self._last_client_seen = 0.0
        self._last_window_launch = 0.0
        if close_window:
            self._close_existing_windows()

    def open_window(self) -> None:
        if not self._url:
            return
        current_time = time.monotonic()
        if current_time - self._last_client_seen < 10 or current_time - self._last_window_launch < 3:
            self._focus_existing_window()
            return
        self._last_window_launch = current_time
        self._close_existing_windows()
        if self._open_chromium_app(self._url):
            return
        webbrowser.open_new(self._url)

    @staticmethod
    def _debugger_window_handles():
        if sys.platform != 'win32':
            return []
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            found = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def enum_callback(hwnd, _):
                length = user32.GetWindowTextLengthW(hwnd)
                if length:
                    title = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, title, length + 1)
                    if 'Lex Talionis Runtime Debugger' in title.value:
                        found.append(hwnd)
                return True

            user32.EnumWindows(enum_callback, 0)
        except (AttributeError, OSError):
            return []
        return found

    @classmethod
    def _focus_existing_window(cls) -> bool:
        handles = cls._debugger_window_handles()
        if handles:
            import ctypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(handles[0], 9)  # SW_RESTORE
            user32.SetForegroundWindow(handles[0])
            return True
        return False

    @classmethod
    def _close_existing_windows(cls) -> None:
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            for hwnd in cls._debugger_window_handles():
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        except (AttributeError, OSError):
            pass

    @staticmethod
    def _open_chromium_app(url: str) -> bool:
        candidates = [
            shutil.which('msedge'),
            shutil.which('chrome'),
        ]
        if sys.platform == 'win32':
            for env_name, relative_paths in (
                    ('PROGRAMFILES(X86)', [Path('Microsoft/Edge/Application/msedge.exe'),
                                          Path('Google/Chrome/Application/chrome.exe')]),
                    ('PROGRAMFILES', [Path('Microsoft/Edge/Application/msedge.exe'),
                                      Path('Google/Chrome/Application/chrome.exe')]),
                    ('LOCALAPPDATA', [Path('Microsoft/Edge/Application/msedge.exe'),
                                      Path('Google/Chrome/Application/chrome.exe')])):
                base = os.environ.get(env_name)
                if base:
                    candidates.extend(str(Path(base, relative)) for relative in relative_paths)
        browser = next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)
        if not browser:
            return False
        kwargs: Dict[str, Any] = {
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
        }
        if sys.platform == 'win32':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        try:
            subprocess.Popen([browser, f'--app={url}', '--new-window'], **kwargs)
            return True
        except OSError:
            return False

    def update(self) -> None:
        if not self._server:
            return
        self._heartbeat += 1
        for _ in range(32):
            try:
                pending = self._commands.get_nowait()
            except queue.Empty:
                break
            try:
                pending.result = self._controller.dispatch(pending.op, pending.args)
            except Exception as exc:
                pending.result = {'ok': False, 'message': str(exc)}
            finally:
                pending.complete.set()

        current_time = time.monotonic()
        if current_time - self._last_snapshot_time >= 0.25:
            try:
                snapshot = self._controller.build_snapshot(self._heartbeat)
            except Exception as exc:
                with self._snapshot_lock:
                    snapshot = dict(self._snapshot)
                snapshot.update({
                    'runtime_active': False,
                    'heartbeat': self._heartbeat,
                    'runtime_error': str(exc),
                })
            with self._snapshot_lock:
                self._snapshot = snapshot
            self._last_snapshot_time = current_time

    def _build_snapshot(self) -> Dict[str, Any]:
        level_nid = game.level.nid if game.level else None
        picking_position = (
            'debug_pick_position' in game.state.state_names() or
            'debug_pick_position' in game.state.temp_state
        )
        hovered_unit_nid = None
        cursor_position = None
        if game.cursor:
            cursor_position = list(game.cursor.position)
            if game.board:
                hovered_unit = game.board.get_unit(game.cursor.position)
                if hovered_unit and 'Tile' not in hovered_unit.tags:
                    hovered_unit_nid = hovered_unit.nid
                    self._selected_unit_nid = hovered_unit_nid
        try:
            money = game.get_money()
        except (AttributeError, KeyError, TypeError):
            money = None
        units = []
        try:
            all_units = game.get_all_units(False)
        except (AttributeError, TypeError):
            all_units = []
        for unit in all_units:
            if 'Tile' in unit.tags:
                continue
            try:
                units.append({
                    'nid': unit.nid,
                    'name': unit.name or unit.nid,
                    'team': unit.team,
                    'level': unit.level,
                    'hp': unit.get_hp(),
                    'max_hp': unit.get_max_hp(),
                    'position': list(unit.position) if unit.position else None,
                })
            except (AttributeError, KeyError, TypeError):
                continue
        units.sort(key=lambda unit: (unit['team'], unit['name'], unit['nid']))
        return {
            'runtime_active': True,
            'heartbeat': self._heartbeat,
            'picked_position': self._picked_position,
            'picking_position': picking_position,
            'notification': self._notification,
            'level': level_nid,
            'turncount': game.turncount,
            'money': money,
            'turnwheel': {
                'current_uses': game.game_vars.get('_current_turnwheel_uses', -1),
                'max_uses': game.game_vars.get('_max_turnwheel_uses', -1),
                'enabled': bool(game.game_vars.get('_turnwheel', False)),
            },
            'cursor_position': cursor_position,
            'hovered_unit_nid': hovered_unit_nid,
            'weather': [weather.nid for weather in game.tilemap.weather] if game.tilemap else [],
            'units': units,
            **self._catalog,
        }

    @staticmethod
    def _event_arg_name(command_type, arg_text: str, arg_idx: int) -> Optional[str]:
        if '=' in arg_text:
            maybe_keyword, _ = arg_text.split('=', 1)
            if command_type.get_validator_from_keyword(maybe_keyword):
                return maybe_keyword
        if arg_idx >= len(command_type.get_keywords()):
            return None
        return command_type.get_keyword_from_index(arg_idx)

    @staticmethod
    def _event_completion_words(arg_text: str) -> tuple[str, str]:
        word_to_match = re.split(r'[^a-zA-Z0-9_ ]', arg_text)[-1]
        word_to_replace = re.split(r"""[^a-zA-Z0-9_ "'{]""", arg_text)[-1]
        return word_to_match, word_to_replace

    def _event_suggestions(self, line: str, source: str) -> Dict[str, Any]:
        parsed = event_commands.parse_event_line(line)
        arg_text = parsed.tokens[-1] if parsed.tokens else ''
        query, replacement = self._event_completion_words(arg_text)
        entries: List[Dict[str, str]] = []
        context = 'Command'

        def add_entry(name: Any, nid: Any, kind: str, entry_context: str) -> None:
            if nid is None:
                return
            value = str(nid)
            display_name = str(name) if name is not None else ''
            display = (
                f'{display_name} ({value})'
                if display_name and display_name != value else value
            )
            entries.append({
                'display': display,
                'match': display,
                'value': value,
                'kind': kind,
                'context': entry_context,
            })

        if parsed.mode() == ParseMode.COMMAND:
            for name, nid in event_validators.EventFunction(DB, RESOURCES).valid_entries():
                add_entry(name, nid, 'normal', context)
        else:
            command_type = event_commands.get_all_event_commands(EventVersion.EVENT).get(
                parsed.command())
            if command_type and parsed.mode() == ParseMode.ARGS:
                arg_name = self._event_arg_name(
                    command_type, arg_text, len(parsed.tokens) - 2)
                validator_nid = command_type.get_validator_from_keyword(arg_name)
                validator_type = event_validators.get(validator_nid)
                context = (
                    f'{validator_nid} - {arg_name}'
                    if validator_nid and arg_name else str(arg_name or 'Argument')
                )
                if validator_type:
                    level_nid = game.level.nid if game.level else None
                    for name, nid in validator_type(DB, RESOURCES).valid_entries(
                            level_nid, arg_text):
                        add_entry(name, nid, 'normal', context)
                    if validator_type.include_generic_completions and len(arg_text) >= 2:
                        words = Counter(source.replace('\n', ' ').replace(';', ' ').split())
                        words[arg_text] -= 1
                        for word, count in words.items():
                            if count > 0 and re.fullmatch(r'[A-Za-z_]+', word) and len(word) > 3:
                                generic_value = self._event_completion_words(word)[1]
                                add_entry(
                                    generic_value, generic_value, 'generic',
                                    f'Text in this command - {arg_name}')
                if arg_name in command_type.optional_keywords:
                    for flag in command_type().flags:
                        add_entry(f'FLAG({flag})', flag, 'flag', f'Flag - {command_type.nid}')
            elif command_type and parsed.mode() == ParseMode.FLAGS:
                context = f'Flag - {command_type.nid}'
                for flag in command_type().flags:
                    add_entry(f'FLAG({flag})', flag, 'flag', context)

        unique_entries: List[Dict[str, str]] = []
        seen = set()
        for entry in entries:
            identity = (entry['value'], entry['kind'])
            if identity not in seen:
                seen.add(identity)
                unique_entries.append(entry)

        lowered_query = query.lower()
        if lowered_query:
            unique_entries = [
                entry for entry in unique_entries
                if lowered_query in entry['match'].lower()
            ]
        unique_entries.sort(
            key=lambda entry: (
                (0.5 if entry['match'].lower().startswith(lowered_query) else 0) +
                SequenceMatcher(
                    None, lowered_query, entry['match'].lower()).ratio()
            ),
            reverse=True)
        for entry in unique_entries:
            entry.pop('match', None)
        return {
            'ok': True,
            'suggestions': unique_entries,
            'replace_length': len(replacement),
            'query': query,
            'context': context,
        }

    @staticmethod
    def _build_command_catalog():
        commands = []
        seen = set()
        for command_type in event_commands.get_all_event_commands(EventVersion.EVENT).values():
            if command_type in seen or command_type.tag == event_commands.Tags.HIDDEN:
                continue
            seen.add(command_type)
            command = command_type()
            keyword_types = command.get_keyword_types()
            arguments = []
            for idx, keyword in enumerate(command.keywords + command.optional_keywords):
                keyword_type = keyword_types[idx] if idx < len(keyword_types) else keyword
                validator = event_validators.get(keyword_type)
                validator_desc = str(getattr(validator, 'desc', '') or '').strip()
                arguments.append({
                    'name': keyword,
                    'type': keyword_type,
                    'optional': idx >= len(command.keywords),
                    'description': validator_desc,
                })
            signature_parts = [
                f"{argument['name']}={argument['type']}" +
                ('?' if argument['optional'] else '')
                for argument in arguments
            ]
            signature = command.nid
            if signature_parts:
                signature += ';' + ';'.join(signature_parts)
            template_parts = [
                f"[{argument['name']}]" if argument['optional'] else f"<{argument['name']}>"
                for argument in arguments
            ]
            template = command.nid
            if template_parts:
                template += ';' + ';'.join(template_parts)
            commands.append({
                'nid': command.nid,
                'nickname': command.nickname,
                'category': command.tag.value,
                'signature': signature,
                'template': template,
                'arguments': arguments,
                'flags': command.flags,
                'description': str(command.desc or '').strip(),
            })
        commands.sort(key=lambda command: (command['category'], command['nid']))
        return commands

    def set_picked_position(self, position) -> None:
        self._controller.set_picked_position(position)

    def _publish_notification(self, message: str, ok: bool = True) -> None:
        self._notification_revision += 1
        self._notification = {
            'message': message,
            'ok': ok,
            'revision': self._notification_revision,
        }

    def handle_hotkey(self, op: str) -> None:
        self._controller.handle_hotkey(op)

    @staticmethod
    def _get_unit(nid: str):
        unit = game.get_unit(nid)
        if not unit:
            raise ValueError(f'Unit {nid!r} is not loaded.')
        return unit

    @staticmethod
    def _unit_detail(unit) -> Dict[str, Any]:
        return {
            'nid': unit.nid,
            'name': unit.name or unit.nid,
            'team': unit.team,
            'klass': unit.klass,
            'position': list(unit.position) if unit.position else None,
            'inventory': [item.nid for item in unit.items],
            'fields': [
                {
                    'key': debug_field.key,
                    'label': debug_field.label,
                    'value': debug_field.value,
                    'minimum': debug_field.minimum,
                    'maximum': debug_field.maximum,
                }
                for debug_field in RuntimeDebugger.editable_fields(unit)
            ],
        }

    def _dispatch(self, op: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if op == 'inspect_unit':
            unit = self._get_unit(str(args.get('nid', '')))
            return {'ok': True, 'detail': self._unit_detail(unit)}
        if op == 'focus_unit':
            unit = self._get_unit(str(args.get('nid', '')))
            if not unit.position or not game.cursor:
                raise ValueError(f'{unit.nid} is not currently on the chapter map.')
            self._selected_unit_nid = unit.nid
            game.cursor.set_pos(unit.position)
            game.cursor.show()
            return {'ok': True, 'message': f'Game cursor moved to {unit.nid}.'}
        if op == 'set_field':
            unit = self._get_unit(str(args.get('nid', '')))
            field_key = str(args.get('key', ''))
            debug_field = next(
                (field for field in RuntimeDebugger.editable_fields(unit) if field.key == field_key),
                None)
            if not debug_field:
                raise ValueError(f'Unknown unit field {field_key!r}.')
            value = RuntimeDebugger.set_unit_field(unit, debug_field, int(args.get('value', 0)))
            return {'ok': True, 'message': f'{debug_field.label} set to {value}.'}
        if op == 'max_unit':
            unit = self._get_unit(str(args.get('nid', '')))
            RuntimeDebugger.max_out_unit(unit)
            return {'ok': True, 'message': f'Maxed {unit.nid}.'}
        if op == 'give_item':
            unit = self._get_unit(str(args.get('nid', '')))
            item_nid = str(args.get('item_nid', ''))
            uses = args.get('uses')
            if uses is not None:
                uses = int(uses)
            if not RuntimeDebugger.give_item(unit, item_nid, uses):
                raise ValueError(
                    f'Could not give item {item_nid!r}; check the item ID and inventory space.')
            uses_text = f' with {uses} use(s)' if uses is not None else ''
            return {'ok': True, 'message': f'Gave {item_nid}{uses_text} to {unit.nid}.'}
        if op == 'teleport':
            unit = self._get_unit(str(args.get('nid', '')))
            success, message = RuntimeDebugger.teleport(
                unit, (int(args.get('x', 0)), int(args.get('y', 0))))
            if not success:
                raise ValueError(message)
            return {'ok': True, 'message': message}
        if op == 'begin_pick_position':
            if not game.level or not game.cursor:
                raise ValueError('A chapter map must be active to pick a position.')
            picker_active = (
                'debug_pick_position' in game.state.state_names() or
                'debug_pick_position' in game.state.temp_state
            )
            if not picker_active:
                game.state.change('debug_pick_position')
            return {
                'ok': True,
                'message': 'Pick a tile in the game and press SELECT; BACK cancels.',
            }
        if op == 'max_players':
            count = RuntimeDebugger.max_out_units(RuntimeDebugger.player_units())
            return {'ok': True, 'message': f'Maxed {count} player unit(s).'}
        if op == 'max_enemies':
            count = RuntimeDebugger.max_out_units(RuntimeDebugger.enemy_units())
            return {'ok': True, 'message': f'Maxed {count} enemy unit(s).'}
        if op == 'enemy_hp':
            count = RuntimeDebugger.set_enemy_hp_to_one()
            return {'ok': True, 'message': f'Set HP to 1 for {count} enemy unit(s).'}
        if op == 'enemy_ai':
            count = RuntimeDebugger.disable_enemy_ai()
            return {'ok': True, 'message': f'Disabled AI for {count} enemy unit(s).'}
        if op == 'complete_chapter':
            RuntimeDebugger.complete_current_chapter()
            return {'ok': True, 'message': 'Completing current chapter...'}
        if op == 'go_chapter':
            level_nid = str(args.get('level_nid', ''))
            if not RuntimeDebugger.go_to_chapter(level_nid):
                raise ValueError(f'Unknown chapter {level_nid!r}.')
            return {'ok': True, 'message': f'Moving to chapter {level_nid}...'}
        if op == 'set_money':
            value = RuntimeDebugger.set_money(int(args.get('value', 0)))
            return {'ok': True, 'message': f'Money set to {value}.'}
        if op == 'set_turn_count':
            value = RuntimeDebugger.set_turn_count(int(args.get('value', 0)))
            return {'ok': True, 'message': f'Turn count set to {value}.'}
        if op == 'set_turnwheel':
            uses, enabled = RuntimeDebugger.set_turnwheel(
                int(args.get('uses', 0)), bool(args.get('enabled', False)))
            status = 'enabled' if enabled else 'disabled'
            uses_label = 'unlimited' if uses == -1 else str(uses)
            return {
                'ok': True,
                'message': f'Turnwheel {status}; current and max uses set to {uses_label}.',
            }
        if op == 'set_weather':
            weather_nid = str(args.get('weather_nid', '')).strip().lower()
            if weather_nid and weather_nid not in event_validators.Weather.valid:
                raise ValueError(f'Unknown weather {weather_nid!r}.')
            RuntimeDebugger.set_weather(weather_nid or None)
            label = weather_nid or 'None'
            return {'ok': True, 'message': f'Weather changed to {label}.'}
        if op == 'event_suggestions':
            line = str(args.get('line', ''))[-8192:]
            source = str(args.get('source', ''))[-65536:]
            return self._event_suggestions(line, source)
        if op == 'event_command':
            script = str(args.get('script', '')).strip()
            parsed_command, _ = event_commands.parse_text_to_command(script)
            if not parsed_command:
                raise ValueError('Invalid event command.')
            unit_nid = args.get('nid')
            unit = game.get_unit(str(unit_nid)) if unit_nid else None
            position = unit.position if unit and unit.position else None
            game.events._add_event_from_script(
                'runtime_debugger', script,
                GenericTrigger(unit1=unit, position=position))
            return {'ok': True, 'message': 'Event command queued.'}
        raise ValueError(f'Unknown debugger operation {op!r}.')

    def _make_handler(self):
        service = self

        class DebuggerRequestHandler(BaseHTTPRequestHandler):
            def log_message(self, format_string, *args):
                return

            def _authorized(self, query: Dict[str, Any]) -> bool:
                supplied = query.get('token', [''])[0]
                return secrets.compare_digest(supplied, service._token)

            def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
                encoded = json.dumps(payload).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(encoded)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                if not self._authorized(query):
                    self._send_json(HTTPStatus.FORBIDDEN, {'ok': False, 'message': 'Forbidden'})
                    return
                if parsed.path == '/api/state':
                    service._last_client_seen = time.monotonic()
                    with service._snapshot_lock:
                        snapshot = dict(service._snapshot)
                    self._send_json(HTTPStatus.OK, snapshot)
                    return
                if parsed.path == '/api/icon':
                    sheet_nid = query.get('sheet', [''])[0]
                    icon_sheet = RESOURCES.icons16.get(sheet_nid)
                    icon_path = Path(icon_sheet.full_path) if icon_sheet and icon_sheet.full_path else None
                    if not icon_path or not icon_path.is_file():
                        self._send_json(
                            HTTPStatus.NOT_FOUND,
                            {'ok': False, 'message': 'Icon sheet not found'})
                        return
                    encoded = icon_path.read_bytes()
                    self.send_response(HTTPStatus.OK)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(encoded)))
                    self.send_header('Cache-Control', 'private, max-age=3600')
                    self.end_headers()
                    self.wfile.write(encoded)
                    return
                if parsed.path in ('/', '/index.html'):
                    encoded = DEBUGGER_PAGE.encode('utf-8')
                    self.send_response(HTTPStatus.OK)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(encoded)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.wfile.write(encoded)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {'ok': False, 'message': 'Not found'})

            def do_POST(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                if not self._authorized(query):
                    self._send_json(HTTPStatus.FORBIDDEN, {'ok': False, 'message': 'Forbidden'})
                    return
                if parsed.path == '/api/window-closed':
                    service._last_client_seen = 0.0
                    self._send_json(HTTPStatus.OK, {'ok': True})
                    return
                if parsed.path != '/api/command':
                    self._send_json(HTTPStatus.NOT_FOUND, {'ok': False, 'message': 'Not found'})
                    return
                try:
                    content_length = min(int(self.headers.get('Content-Length', '0')), 64 * 1024)
                    payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
                    pending = PendingCommand(str(payload.get('op', '')), payload.get('args') or {})
                    service._commands.put(pending)
                    if not pending.complete.wait(timeout=3):
                        self._send_json(
                            HTTPStatus.GATEWAY_TIMEOUT,
                            {'ok': False, 'message': 'Game did not process the command in time.'})
                        return
                    status = HTTPStatus.OK if pending.result.get('ok') else HTTPStatus.BAD_REQUEST
                    self._send_json(status, pending.result)
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'message': str(exc)})

        return DebuggerRequestHandler


SERVICE = RuntimeDebuggerService()


def start() -> None:
    from app.engine import config as cf
    if cf.SETTINGS['debug']:
        SERVICE.start()


def update() -> None:
    SERVICE.update()


def open_window() -> None:
    SERVICE.open_window()


def ensure_window() -> None:
    from app.engine import config as cf
    if not cf.SETTINGS['debug']:
        SERVICE.stop(close_window=True)
        return
    if SERVICE.url:
        SERVICE.open_window()
    else:
        SERVICE.start()


def set_picked_position(position) -> None:
    SERVICE.set_picked_position(position)


def handle_hotkey(op: str) -> None:
    SERVICE.handle_hotkey(op)


def stop(close_window: bool = True) -> None:
    SERVICE.stop(close_window=close_window)


atexit.register(stop)
