const axios = require("axios");

const GRAPH_BASE = "https://graph.microsoft.com/v1.0";

function encodeODataString(s) {
  return "'" + String(s).replace(/'/g, "''") + "'";
}
function chunkArray(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}
function buildOrEquals(field, values) {
  return "(" + values.map((v) => `${field} eq ${encodeODataString(v)}`).join(" or ") + ")";
}
function toMs(dt) {
  const t = Date.parse(dt);
  return Number.isFinite(t) ? t : NaN;
}
function subtractHoursIso(hours) {
  const d = new Date(Date.now() - hours * 60 * 60 * 1000);
  return d.toISOString();
}

async function pagedGet({ url, headers, params, maxPages }) {
  const pages = [];
  let next = null;
  let page = 0;

  do {
    page++;
    const res = next
      ? await axios.get(next, { headers })
      : await axios.get(url, { headers, params });

    pages.push(res);
    next = res.data?.["@odata.nextLink"] || null;
  } while (next && page < maxPages);

  return pages;
}

const LOG_PREFIX = "[list-outlook-unanswered]";

async function handler(inputs) {
  const token = process.env.OUTLOOK_API_KEY;
  if (!token) throw new Error("OUTLOOK_API_KEY not set");

  const {
    senderDomain,
    windowHours = 72,
    pageSize = 100,
    maxInboxPages = 3,
    maxSentPages = 3,
    draftChunkSize = 15,
    onlyEdurataDrafts = false,
    maxUnanswered = 10,
  } = inputs || {};

  if (!senderDomain) {
    throw new Error("senderDomain is required");
  }

  const sinceDateTime = subtractHoursIso(Number(windowHours) || 72);
  console.log(
    `${LOG_PREFIX} start senderDomain=${senderDomain} windowHours=${windowHours} sinceUsed=${sinceDateTime} maxUnanswered=${maxUnanswered}`
  );

  const headers = {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };

  /* ===============================
     1) INBOX BULK PULL
  =============================== */

  const inboxPages = await pagedGet({
    url: `${GRAPH_BASE}/me/mailFolders/inbox/messages`,
    headers,
    params: {
      $filter: `receivedDateTime ge ${sinceDateTime} and contains(from/emailAddress/address,${encodeODataString(senderDomain)})`,
      $top: Math.min(pageSize, 100),
      $select: "id,receivedDateTime,conversationId",
      $orderby: "receivedDateTime desc",
    },
    maxPages: maxInboxPages,
  });

  const inboxMsgs = inboxPages.flatMap((p) => p.data?.value || []);
  console.log(
    `${LOG_PREFIX} inbox: ${inboxPages.length} page(s), ${inboxMsgs.length} message(s) from domain`
  );

  // Latest inbound per conversation
  const latestInboundByCid = new Map();
  for (const m of inboxMsgs) {
    if (!m.conversationId || !m.receivedDateTime) continue;
    const cur = latestInboundByCid.get(m.conversationId);
    if (!cur || m.receivedDateTime > cur.receivedDateTime) {
      latestInboundByCid.set(m.conversationId, {
        id: m.id,
        receivedDateTime: m.receivedDateTime,
      });
    }
  }

  const allConversationIds = Array.from(latestInboundByCid.keys());
  console.log(
    `${LOG_PREFIX} inbox: ${allConversationIds.length} unique conversation(s) (latest inbound per cid)`
  );
  if (allConversationIds.length === 0) {
    console.log(`${LOG_PREFIX} early return: no conversations in window`);
    return {
      unansweredConversationIds: [],
      answeredConversationIds: [],
      countUnanswered: 0,
      countAnswered: 0,
      sinceUsed: sinceDateTime,
    };
  }

  /* ===============================
     2) SENT ITEMS BULK PULL
  =============================== */

  const sentPages = await pagedGet({
    url: `${GRAPH_BASE}/me/mailFolders/sentitems/messages`,
    headers,
    params: {
      $filter: `sentDateTime ge ${sinceDateTime}`,
      $top: Math.min(pageSize, 100),
      $select: "conversationId,sentDateTime",
      $orderby: "sentDateTime desc",
    },
    maxPages: maxSentPages,
  });

  const sentMsgs = sentPages.flatMap((p) => p.data?.value || []);
  console.log(
    `${LOG_PREFIX} sent: ${sentPages.length} page(s), ${sentMsgs.length} message(s) in window`
  );

  const latestSentByCid = new Map();
  for (const s of sentMsgs) {
    if (!s.conversationId || !s.sentDateTime) continue;
    if (!latestInboundByCid.has(s.conversationId)) continue;
    const cur = latestSentByCid.get(s.conversationId);
    if (!cur || s.sentDateTime > cur) {
      latestSentByCid.set(s.conversationId, s.sentDateTime);
    }
  }
  const cidsWithSent = [...latestSentByCid.keys()].filter((cid) =>
    allConversationIds.includes(cid)
  ).length;
  console.log(
    `${LOG_PREFIX} sent: ${cidsWithSent} of ${allConversationIds.length} conversation(s) have sent message in window`
  );

  /* ===============================
     3) DRAFT BULK CHECK
  =============================== */

  const newestDraftByCid = new Map();
  const chunks = chunkArray(allConversationIds, draftChunkSize);

  for (const chunk of chunks) {
    let filter = `isDraft eq true and ${buildOrEquals("conversationId", chunk)}`;
    if (onlyEdurataDrafts) {
      filter += ` and categories/any(c: c eq ${encodeODataString("EdurataDraft")})`;
    }

    const res = await axios.get(`${GRAPH_BASE}/me/mailFolders/drafts/messages`, {
      headers,
      params: {
        $filter: filter,
        $top: 200,
        $select: "id,conversationId,lastModifiedDateTime",
      },
    });

    const drafts = res.data?.value || [];
    for (const d of drafts) {
      const cur = newestDraftByCid.get(d.conversationId);
      if (!cur || d.lastModifiedDateTime > cur.lastModifiedDateTime) {
        newestDraftByCid.set(d.conversationId, {
          id: d.id,
          lastModifiedDateTime: d.lastModifiedDateTime,
        });
      }
    }
  }
  const totalDrafts = newestDraftByCid.size;
  console.log(
    `${LOG_PREFIX} drafts: ${totalDrafts} conversation(s) have draft(s) (onlyEdurataDrafts=${onlyEdurataDrafts})`
  );

  /* ===============================
     4) CLASSIFICATION
  =============================== */

  const unansweredConversationIds = [];
  const answeredConversationIds = [];

  for (const cid of allConversationIds) {
    const inbound = latestInboundByCid.get(cid);
    const inboundMs = toMs(inbound.receivedDateTime);
    const sentMs = toMs(latestSentByCid.get(cid));

    const isAnswered =
      Number.isFinite(sentMs) &&
      Number.isFinite(inboundMs) &&
      sentMs > inboundMs;

    if (isAnswered) {
      answeredConversationIds.push(cid);
      continue;
    }

    const draft = newestDraftByCid.get(cid);
    if (!draft) {
      unansweredConversationIds.push(cid);
      continue;
    }

    const draftMs = toMs(draft.lastModifiedDateTime);
    const isOutdated =
      Number.isFinite(draftMs) &&
      Number.isFinite(inboundMs) &&
      draftMs < inboundMs;

    if (isOutdated) {
      unansweredConversationIds.push(cid);
    }
  }

  const limit = Math.max(0, Number(maxUnanswered) || 0);
  const cappedIds = limit > 0 ? unansweredConversationIds.slice(0, limit) : unansweredConversationIds;

  console.log(
    `${LOG_PREFIX} classification: answered=${answeredConversationIds.length} unanswered=${unansweredConversationIds.length} (returning ${cappedIds.length} after maxUnanswered=${limit})`
  );

  return {
    unansweredConversationIds: cappedIds,
    answeredConversationIds,
    countUnanswered: unansweredConversationIds.length,
    countAnswered: answeredConversationIds.length,
    sinceUsed: sinceDateTime,
  };
}

module.exports = { handler };
