// Freya Bank mock (Cloudflare Worker). Placeholder until the final integration document (section 6) and the test
// customers are implemented: only GET /health answers; every other path is 404 with a JSON body.
export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/health") {
      return Response.json({ ok: true, service: "freya-bank-mock", version: "placeholder" });
    }
    return Response.json({ error: "not_found", path: url.pathname }, { status: 404 });
  },
};
