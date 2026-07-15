import "@testing-library/jest-dom/vitest";

// jsdom no implementa scrollIntoView (usado en ChatWidget para el autoscroll
// del historial de mensajes). No es un bug real, es una limitación del
// entorno de test que hay que rellenar.
Element.prototype.scrollIntoView = () => {};

// ChatWidget llama a fetch("/health") directo (no vía services/api.js) en un
// useEffect para chequear disponibilidad de Vertex AI. Sin este mock, en
// jsdom esa llamada intenta ir a la red real y puede colgar los tests.
global.fetch = () =>
  Promise.resolve({ json: () => Promise.resolve({ ai_available: true }) });