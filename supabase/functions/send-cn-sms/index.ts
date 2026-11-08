import { Buffer } from "node:buffer";
import { createHash, createHmac, timingSafeEqual } from "node:crypto";

const host = "sms.tencentcloudapi.com";
const contentType = "application/json; charset=utf-8";

function failure(status: number, message: string) {
  return Response.json({ error: { http_code: status, message } }, { status });
}

// Standard Webhooks v1 signs the message ID, original timestamp and exact body bytes.
async function verifiedPayload(req: Request, secret: Buffer) {
  const id = req.headers.get("webhook-id");
  const timestamp = req.headers.get("webhook-timestamp") ?? "";
  const signatures = req.headers.get("webhook-signature");
  if (!id || !signatures || !/^\d+$/.test(timestamp) ||
      Math.abs(Math.floor(Date.now() / 1000) - Number(timestamp)) > 300) return null;

  const body = Buffer.from(await req.arrayBuffer());
  const expected = createHmac("sha256", secret).update(`${id}.${timestamp}.`).update(body).digest();
  const verified = signatures.split(" ").some((signature) => {
    if (!/^v1,[A-Za-z0-9+/]{43}=$/.test(signature)) return false;
    return timingSafeEqual(expected, Buffer.from(signature.slice(3), "base64"));
  });
  return verified ? body : null;
}

function hash(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

function hmac(key: string | Buffer, value: string) {
  return createHmac("sha256", key).update(value).digest();
}

function signedHeaders(body: string, secretId: string, secretKey: string, region: string) {
  const timestamp = Math.floor(Date.now() / 1000);
  const date = new Date(timestamp * 1000).toISOString().slice(0, 10);
  const scope = `${date}/sms/tc3_request`;
  const headers = "content-type;host;x-tc-action";
  const canonical = `POST\n/\n\ncontent-type:${contentType}\nhost:${host}\nx-tc-action:sendsms\n\n${headers}\n${hash(body)}`;
  const toSign = `TC3-HMAC-SHA256\n${timestamp}\n${scope}\n${hash(canonical)}`;
  const dayKey = hmac(`TC3${secretKey}`, date);
  const signingKey = hmac(hmac(dayKey, "sms"), "tc3_request");
  return {
    "Content-Type": contentType,
    "X-TC-Action": "SendSms",
    "X-TC-Version": "2021-01-11",
    "X-TC-Region": region,
    "X-TC-Timestamp": String(timestamp),
    Authorization: `TC3-HMAC-SHA256 Credential=${secretId}/${scope}, SignedHeaders=${headers}, Signature=${hmac(signingKey, toSign).toString("hex")}`,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return failure(405, "请求方式错误");
  const hookSecret = Deno.env.get("SEND_SMS_HOOK_SECRET")?.match(/^v1,whsec_([A-Za-z0-9+/]+={0,2})$/)?.[1];
  if (!hookSecret) return failure(500, "短信服务尚未配置");
  const payload = await verifiedPayload(req, Buffer.from(hookSecret, "base64"));
  if (!payload) return failure(401, "短信请求签名无效");

  let event;
  try {
    event = JSON.parse(payload.toString("utf8"));
  } catch {
    return failure(400, "短信请求格式错误");
  }
  const sms = event?.sms;
  const user = event?.user;
  // Older Auth versions omit sms.phone. Never guess between two possible recipients.
  const legacyPhone = user?.new_phone && user?.phone ? null : user?.new_phone || user?.phone;
  const target = sms?.phone ?? legacyPhone;
  const otp = sms?.otp;
  if (typeof target !== "string" || !/^\+?861[3-9]\d{9}$/.test(target) ||
      typeof otp !== "string" || !/^\d{6}$/.test(otp)) return failure(422, "验证码或大陆手机号格式错误");

  const secretId = Deno.env.get("TENCENTCLOUD_SECRET_ID");
  const secretKey = Deno.env.get("TENCENTCLOUD_SECRET_KEY");
  const appId = Deno.env.get("TENCENT_SMS_SDK_APP_ID");
  const signName = Deno.env.get("TENCENT_SMS_SIGN_NAME");
  const templateId = Deno.env.get("TENCENT_SMS_TEMPLATE_ID");
  if (!secretId || !secretKey || !appId || !signName || !templateId) return failure(500, "短信服务尚未配置");
  const body = JSON.stringify({
    PhoneNumberSet: [target.startsWith("+") ? target : `+${target}`],
    SmsSdkAppId: appId,
    SignName: signName,
    TemplateId: templateId,
    TemplateParamSet: [otp],
  });
  try {
    const response = await fetch(`https://${host}/`, {
      method: "POST",
      headers: signedHeaders(body, secretId, secretKey, Deno.env.get("TENCENT_SMS_REGION") || "ap-guangzhou"),
      body,
      redirect: "error",
      signal: AbortSignal.timeout(3500),
    });
    if (response.ok) {
      const result = (await response.json()).Response;
      if (!result?.Error && result?.SendStatusSet?.length === 1 && result.SendStatusSet[0]?.Code === "Ok") {
        return new Response(null, { status: 200 });
      }
    }
  } catch {
    // Raw provider errors and request bodies can contain the recipient or OTP.
  }
  return failure(502, "短信服务发送失败，请稍后重试");
});
