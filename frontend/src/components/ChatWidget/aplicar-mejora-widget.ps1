$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")
$widgetPath = Join-Path $projectRoot "frontend\src\components\ChatWidget\index.jsx"
$cssSource = Join-Path $PSScriptRoot "chat-widget-polish.css"
$cssTarget = Join-Path $projectRoot "frontend\src\components\ChatWidget\chat-widget-polish.css"

if (-not (Test-Path $widgetPath)) {
    throw "No se encontró: $widgetPath"
}

Copy-Item $widgetPath "$widgetPath.bak" -Force
Copy-Item $cssSource $cssTarget -Force

$content = Get-Content $widgetPath -Raw

if ($content -notmatch 'chat-widget-polish\.css') {
    $content = $content.Replace(
        'import BotiqBotIcon from "../Brand/BotiqBotIcon";',
        'import BotiqBotIcon from "../Brand/BotiqBotIcon";' + "`r`n" + 'import "./chat-widget-polish.css";'
    )
}

$content = $content.Replace(
    'className="botiq-chat-float-button" style={{ ...floatBtn(primaryColor), pointerEvents: "auto" }}',
    'className={`botiq-chat-float-button ${open ? "is-open" : ""}`} style={{ ...floatBtn(primaryColor), pointerEvents: "auto" }}'
)

$content = $content.Replace(
    '<span style={{ color: "#fff", fontSize: 20 }}>✕</span>',
    '<span className="botiq-chat-float-button__close" aria-hidden="true" />'
)

$content = $content.Replace(
    '<BotiqBotIcon size={31} color={primaryColor} light />',
    '<><BotiqBotIcon size={31} color={primaryColor} light /><span className="botiq-chat-float-button__badge" aria-hidden="true" /></>'
)

$content = $content.Replace(
    '</button>' + "`r`n" + "`r`n" + '      <style>',
    '</button>' + "`r`n" + '      <span className="botiq-chat-float-label">{open ? "Cerrar asistente" : "Abrir BOTIQ"}</span>' + "`r`n" + "`r`n" + '      <style>'
)

$content = $content.Replace(
    '<div style={{ background: `linear-gradient(135deg, ${primaryColor}, ${CL})`, padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>',
    '<div className="botiq-chat-header" style={{ background: `linear-gradient(135deg, ${primaryColor}, ${CL})`, padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>'
)

$content = $content.Replace(
    '<div style={{ display: "flex", alignItems: "center", gap: 10 }}>',
    '<div className="botiq-chat-header__identity" style={{ display: "flex", alignItems: "center", gap: 10 }}>'
)

$content = $content.Replace(
    '<div style={{ color: "#fff", fontWeight: 800, fontSize: 15 }}>BOTIQ</div>',
    '<div className="botiq-chat-header__title" style={{ color: "#fff", fontWeight: 800, fontSize: 15 }}>BOTIQ</div>'
)

$content = $content.Replace(
    '<div style={{ color: "rgba(255,255,255,0.68)", fontSize: 11 }}>Asistente IA corporativo</div>',
    '<div className="botiq-chat-header__subtitle" style={{ color: "rgba(255,255,255,0.68)", fontSize: 11 }}>Asistente IA corporativo</div>'
)

$content = $content.Replace(
    '<div style={{ display: "flex", gap: 5 }}>',
    '<div className="botiq-chat-header__actions" style={{ display: "flex", gap: 5 }}>'
)

$content = $content.Replace(
    'style={{ background: "rgba(255,255,255,0.11)", border: "1px solid rgba(255,255,255,0.2)", color: "rgba(255,255,255,0.76)", width: 28, height: 28, borderRadius: 8, cursor: "pointer" }}',
    'className="botiq-chat-header__button" style={{ background: "rgba(255,255,255,0.11)", border: "1px solid rgba(255,255,255,0.2)", color: "rgba(255,255,255,0.76)", width: 28, height: 28, borderRadius: 8, cursor: "pointer" }}'
)

$content = $content.Replace(
    '<div style={{ textAlign: "center", padding: "22px 6px" }}>',
    '<div className="botiq-profile-selector" style={{ textAlign: "center", padding: "22px 6px" }}>'
)

$content = $content.Replace(
    '<div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>',
    '<div className="botiq-profile-selector__avatar" style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>'
)

$content = $content.Replace(
    '<p style={{ fontWeight: 800, color: primaryColor, fontSize: 16, marginBottom: 6 }}>',
    '<p className="botiq-profile-selector__title" style={{ fontWeight: 800, color: primaryColor, fontSize: 16, marginBottom: 6 }}>'
)

$content = $content.Replace(
    '<p style={{ color: "#6b6b8a", fontSize: 12, marginBottom: 16, lineHeight: 1.6 }}>',
    '<p className="botiq-profile-selector__description" style={{ color: "#6b6b8a", fontSize: 12, marginBottom: 16, lineHeight: 1.6 }}>'
)

$content = $content.Replace(
    'style={profileBtn(primaryColor, selectedProfile === "employee")}',
    'className={`botiq-profile-card ${selectedProfile === "employee" ? "is-active" : ""}`} style={profileBtn(primaryColor, selectedProfile === "employee")}'
)

$content = $content.Replace(
    'style={profileBtn(primaryColor, selectedProfile === "support_engineer")}',
    'className={`botiq-profile-card ${selectedProfile === "support_engineer" ? "is-active" : ""}`} style={profileBtn(primaryColor, selectedProfile === "support_engineer")}'
)

$content = $content.Replace(
    '<div style={{ marginTop: 14, textAlign: "left" }}>',
    '<div className="botiq-support-access" style={{ marginTop: 14, textAlign: "left" }}>'
)

$content = $content.Replace(
    '<label style={{ fontSize: 11, color: "#374151", fontWeight: 700 }}>',
    '<label className="botiq-support-access__label" style={{ fontSize: 11, color: "#374151", fontWeight: 700 }}>'
)

$content = $content.Replace(
    'placeholder="ej: jose.cortez"' + "`r`n" + '          style={{ width: "100%",',
    'placeholder="ej: jose.cortez"' + "`r`n" + '          className="botiq-support-access__input"' + "`r`n" + '          style={{ width: "100%",'
)

$content = $content.Replace(
    '<button disabled={loading} onClick={configureSupport} style={{ marginTop: 10, width: "100%",',
    '<button disabled={loading} onClick={configureSupport} className="botiq-support-access__button" style={{ marginTop: 10, width: "100%",'
)

$content = $content.Replace(
    '<div style={{ marginTop: 14, fontSize: 11, color: "#6b6b8a", lineHeight: 1.5 }}>',
    '<div className="botiq-profile-selector__notice" style={{ marginTop: 14, fontSize: 11, color: "#6b6b8a", lineHeight: 1.5 }}>'
)

Set-Content -Path $widgetPath -Value $content -Encoding UTF8

Write-Host ""
Write-Host "Mejora aplicada correctamente." -ForegroundColor Green
Write-Host "Respaldo creado en: $widgetPath.bak"
Write-Host "CSS copiado en: $cssTarget"
