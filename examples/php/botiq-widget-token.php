<?php
declare(strict_types=1);

/**
 * Endpoint INTERNO del portal:
 *   POST /api/botiq-widget-token.php
 *
 * Requisitos:
 * - El usuario ya inició sesión en el portal.
 * - BOTIQ_PORTAL_SECRET vive en variables de entorno del servidor.
 * - Nunca recibe email/origin desde JavaScript; usa la sesión y configuración.
 */

session_start();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, private, max-age=0');
header('Pragma: no-cache');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['detail' => 'Método no permitido']);
    exit;
}

// Adapta estas claves a la sesión real de tu portal.
$email = trim((string) ($_SESSION['user_email'] ?? ''));
$fullName = trim((string) ($_SESSION['user_full_name'] ?? ''));

if ($email === '' || $fullName === '') {
    http_response_code(401);
    echo json_encode(['detail' => 'Debes iniciar sesión en el portal']);
    exit;
}

$botiqBaseUrl = rtrim(
    getenv('BOTIQ_BASE_URL') ?: 'https://botiq.tu-dominio.com',
    '/'
);
$portalId = getenv('BOTIQ_PORTAL_ID') ?: 'portal-icetex';
$portalSecret = getenv('BOTIQ_PORTAL_SECRET') ?: '';
$portalOrigin = getenv('BOTIQ_PORTAL_ORIGIN')
    ?: 'https://portal.tu-dominio.com';

if ($portalSecret === '') {
    http_response_code(500);
    echo json_encode(['detail' => 'Integración BOTIQ no configurada']);
    exit;
}

// Defensa CSRF básica para este endpoint del portal.
// Conserva además el mecanismo CSRF propio que ya tenga tu aplicación.
$requestOrigin = (string) ($_SERVER['HTTP_ORIGIN'] ?? '');
if ($requestOrigin !== '' && $requestOrigin !== $portalOrigin) {
    http_response_code(403);
    echo json_encode(['detail' => 'Origin no autorizado']);
    exit;
}

$payload = json_encode([
    'email' => strtolower($email),
    'full_name' => $fullName,
    'origin' => $portalOrigin,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

$ch = curl_init($botiqBaseUrl . '/api/v1/widget/token');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_CONNECTTIMEOUT => 5,
    CURLOPT_TIMEOUT => 12,
    CURLOPT_HTTPHEADER => [
        'Accept: application/json',
        'Content-Type: application/json',
        'X-BOTIQ-Portal-Id: ' . $portalId,
        'X-BOTIQ-Portal-Secret: ' . $portalSecret,
    ],
    CURLOPT_POSTFIELDS => $payload,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_SSL_VERIFYHOST => 2,
]);

$responseBody = curl_exec($ch);
$statusCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curlError = curl_error($ch);
curl_close($ch);

if ($responseBody === false || $curlError !== '') {
    error_log('BOTIQ widget token error: ' . $curlError);
    http_response_code(502);
    echo json_encode([
        'detail' => 'BOTIQ no está disponible temporalmente',
    ]);
    exit;
}

http_response_code($statusCode >= 200 && $statusCode < 500
    ? $statusCode
    : 502);
echo $responseBody;
