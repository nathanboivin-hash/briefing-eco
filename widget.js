// Morning Brief Widget for Scriptable
// Paste this in Scriptable app on your iPhone

const BRIEFING_URL = "https://nathanboivin-hash.github.io/briefing-eco/briefing.json"
const APP_URL = "https://nathanboivin-hash.github.io/briefing-eco/"

const C_INK = new Color("#1a1a1a")
const C_PAPER = new Color("#f5f2ed")
const C_ACCENT = new Color("#c8a46a")
const C_MUTED = new Color("#7a7570")
const C_GREEN = new Color("#2d6e45")
const C_RED = new Color("#c0392b")
const C_DARK = new Color("#0d0e10")
const C_DARK2 = new Color("#15171b")
const C_TEXT = new Color("#ede9e3")
const C_TEXT2 = new Color("#c5c0b8")

async function fetchBriefing() {
  try {
    const req = new Request(BRIEFING_URL + "?t=" + Date.now())
    req.timeoutInterval = 10
    return await req.loadJSON()
  } catch(e) {
    return null
  }
}

function dirColor(dir) {
  if (dir === "up") return C_GREEN
  if (dir === "down") return C_RED
  return C_MUTED
}

function shortText(txt, max) {
  if (!txt) return ""
  return txt.length > max ? txt.substring(0, max - 3) + "..." : txt
}

function buildSmall(w, data) {
  w.backgroundColor = C_DARK
  w.setPadding(14, 14, 14, 14)
  w.url = APP_URL

  var t1 = w.addText("Morning Brief")
  t1.font = Font.italicSystemFont(13)
  t1.textColor = C_ACCENT
  w.addSpacer(4)

  var t2 = w.addText(data.timestamp || "-")
  t2.font = Font.systemFont(9)
  t2.textColor = C_MUTED
  w.addSpacer(8)

  var resume = (data.synthese && data.synthese.resume) ? data.synthese.resume : "Pas de briefing"
  var t3 = w.addText(shortText(resume, 140))
  t3.font = Font.systemFont(11)
  t3.textColor = C_TEXT2
  t3.lineLimit = 5

  w.addSpacer()
  var t4 = w.addText("Ouvrir ->")
  t4.font = Font.systemFont(9)
  t4.textColor = C_ACCENT
}

function buildMedium(w, data) {
  w.backgroundColor = C_DARK
  w.setPadding(14, 16, 14, 16)
  w.url = APP_URL

  var hStack = w.addStack()
  hStack.layoutHorizontally()

  var leftStack = hStack.addStack()
  leftStack.layoutVertically()
  var t1 = leftStack.addText("Morning Brief")
  t1.font = Font.italicSystemFont(15)
  t1.textColor = C_ACCENT
  var t2 = leftStack.addText(data.timestamp || "-")
  t2.font = Font.systemFont(9)
  t2.textColor = C_MUTED

  hStack.addSpacer()

  var metrics = (data.marches && data.marches.metrics) ? data.marches.metrics : []
  if (metrics.length > 0) {
    var mStack = hStack.addStack()
    mStack.layoutVertically()
    mStack.spacing = 3
    for (var i = 0; i < Math.min(2, metrics.length); i++) {
      var m = metrics[i]
      var row = mStack.addStack()
      row.layoutHorizontally()
      var lbl = row.addText(m.label)
      lbl.font = Font.systemFont(9)
      lbl.textColor = C_MUTED
      row.addSpacer()
      var val = row.addText(m.value || "-")
      val.font = Font.boldSystemFont(9)
      val.textColor = C_TEXT
      row.addSpacer(4)
      var chg = row.addText(m.change || "")
      chg.font = Font.systemFont(9)
      chg.textColor = dirColor(m.dir)
    }
  }

  w.addSpacer(8)

  var points = (data.synthese && data.synthese.points) ? data.synthese.points : []
  for (var j = 0; j < Math.min(2, points.length); j++) {
    var p = points[j]
    var pStack = w.addStack()
    pStack.layoutVertically()
    pStack.spacing = 1

    var parts = (p.titre || "").split("-")
    var label = parts.length > 1 ? parts[0].trim() : ""
    var ptitle = parts.length > 1 ? parts.slice(1).join("-").trim() : p.titre

    if (label) {
      var lbTxt = pStack.addText(label.toUpperCase())
      lbTxt.font = Font.semiboldSystemFont(8)
      lbTxt.textColor = C_ACCENT
    }
    var pTxt = pStack.addText(shortText(ptitle, 60))
    pTxt.font = Font.semiboldSystemFont(11)
    pTxt.textColor = C_TEXT
    pTxt.lineLimit = 1

    var dTxt = pStack.addText(shortText(p.detail || "", 80))
    dTxt.font = Font.systemFont(10)
    dTxt.textColor = C_MUTED
    dTxt.lineLimit = 1

    w.addSpacer(4)
  }

  w.addSpacer()
  var tapTxt = w.addText("Ouvrir le briefing complet ->")
  tapTxt.font = Font.systemFont(9)
  tapTxt.textColor = C_ACCENT
}

function buildLarge(w, data) {
  w.backgroundColor = C_DARK
  w.setPadding(16, 18, 16, 18)
  w.url = APP_URL

  var t1 = w.addText("Morning Brief")
  t1.font = Font.italicSystemFont(17)
  t1.textColor = C_ACCENT
  var t2 = w.addText(data.timestamp || "-")
  t2.font = Font.systemFont(9)
  t2.textColor = C_MUTED
  w.addSpacer(10)

  var metrics = (data.marches && data.marches.metrics) ? data.marches.metrics : []
  if (metrics.length > 0) {
    var mRow = w.addStack()
    mRow.layoutHorizontally()
    mRow.spacing = 6
    for (var i = 0; i < Math.min(4, metrics.length); i++) {
      var m = metrics[i]
      var card = mRow.addStack()
      card.layoutVertically()
      card.backgroundColor = C_DARK2
      card.cornerRadius = 6
      card.setPadding(8, 10, 8, 10)
      var lbl = card.addText(m.label)
      lbl.font = Font.systemFont(8)
      lbl.textColor = C_MUTED
      var val = card.addText(m.value || "-")
      val.font = Font.boldSystemFont(13)
      val.textColor = C_TEXT
      var chg = card.addText(m.change || "")
      chg.font = Font.systemFont(9)
      chg.textColor = dirColor(m.dir)
    }
    w.addSpacer(10)
  }

  var resume = (data.synthese && data.synthese.resume) ? data.synthese.resume : ""
  var rTxt = w.addText(shortText(resume, 220))
  rTxt.font = Font.systemFont(11)
  rTxt.textColor = C_TEXT2
  rTxt.lineLimit = 4
  w.addSpacer(8)

  var points = (data.synthese && data.synthese.points) ? data.synthese.points : []
  for (var j = 0; j < Math.min(3, points.length); j++) {
    var p = points[j]
    var pTxt = w.addText("- " + shortText(p.titre || "", 70))
    pTxt.font = Font.semiboldSystemFont(10)
    pTxt.textColor = C_TEXT
    pTxt.lineLimit = 1
    w.addSpacer(2)
  }

  w.addSpacer()
  var tapTxt = w.addText("Ouvrir le briefing complet ->")
  tapTxt.font = Font.systemFont(9)
  tapTxt.textColor = C_ACCENT
}

// MAIN
var widget = new ListWidget()
widget.refreshAfterDate = new Date(Date.now() + 30 * 60 * 1000)

var data = await fetchBriefing()

if (!data) {
  widget.backgroundColor = C_DARK
  var errTxt = widget.addText("Morning Brief")
  errTxt.font = Font.italicSystemFont(14)
  errTxt.textColor = C_ACCENT
  widget.addSpacer(8)
  var msgTxt = widget.addText("Briefing non disponible.")
  msgTxt.font = Font.systemFont(11)
  msgTxt.textColor = C_MUTED
} else {
  var size = config.widgetFamily
  if (size === "small") {
    buildSmall(widget, data)
  } else if (size === "large") {
    buildLarge(widget, data)
  } else {
    buildMedium(widget, data)
  }
}

Script.setWidget(widget)
if (!config.runningInWidget) {
  await widget.presentMedium()
}
Script.complete()
