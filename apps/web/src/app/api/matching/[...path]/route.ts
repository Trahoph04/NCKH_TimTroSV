import { proxyToApi } from "@/lib/proxy";

// /api/matching/* → FastAPI /matching/* (swipe, lời mời).
export const dynamic = "force-dynamic";

type Ctx = { params: { path: string[] } };

const forward = (req: Request, { params }: Ctx) =>
  proxyToApi(req, `/matching/${params.path.map(encodeURIComponent).join("/")}`);

export const GET = forward;
export const POST = forward;
