import { useCallback, useEffect, useRef, useState } from "react";

type RulesetsResponse = { ruleset_ids: string[] };

type FinalItem = {
  title: string;
  comment: string;
  degree: string;
  category: number;
  item_type: string;
  action_type: string;
  change_type?: string;
  revised_text?: string;
  revised_para?: string;
  original_id?: number[];
};

type ReviewResponse = {
  review_id: string;
  status: string;
  summary: Record<string, unknown>;
  markdown_report?: string;
  final_output: {
    comment_list: FinalItem[];
    extracted_info: { title: string; comment: string }[];
  };
};

type DryRunResponse = {
  summary: Record<string, unknown>;
  review_tasks: unknown[];
};

type ErrorCollectionRow = {
  title?: string;
  comment?: string;
  degree?: string;
  source?: string;
};

function flattenFetRows(summary: Record<string, unknown>) {
  const fet = summary.field_extraction_tasks as
    | { mode_0?: unknown[]; mode_1?: unknown[]; mode_23?: unknown[] }
    | undefined;
  if (!fet) return [];
  const rows: { key: string; label: string; row: Record<string, unknown> }[] = [];
  const push = (arr: unknown[] | undefined, prefix: string) => {
    (Array.isArray(arr) ? arr : []).forEach((r, i) => {
      rows.push({
        key: `${prefix}-${i}`,
        label: `${prefix} #${i + 1}`,
        row: typeof r === "object" && r !== null ? (r as Record<string, unknown>) : {},
      });
    });
  };
  push(fet.mode_0, "mode_0");
  push(fet.mode_1, "mode_1");
  push(fet.mode_23, "mode_23");
  return rows;
}

function sourceLibraryOverview(summary: Record<string, unknown>): string {
  const meta = summary.source_library_meta;
  if (Array.isArray(meta) && meta.length) {
    return meta
      .map((m: unknown) => {
        if (typeof m !== "object" || m === null) return "?";
        const o = m as { src?: unknown; content_len?: unknown };
        const len =
          typeof o.content_len === "number" && !Number.isNaN(o.content_len)
            ? o.content_len
            : "—";
        return `src=${String(o.src ?? "?")} · ${len} 字`;
      })
      .join(" · ");
  }
  const lib = summary.source_library;
  if (Array.isArray(lib)) {
    return `${lib.length} 项（无 meta）`;
  }
  return "—";
}

function fetCounts(summary: Record<string, unknown>): string {
  const c = summary.field_extraction_task_counts as Record<string, unknown> | undefined;
  if (!c) return "—";
  return `mode_0=${String(c.mode_0 ?? "—")} · mode_1=${String(c.mode_1 ?? "—")} · mode_23=${String(c.mode_23 ?? "—")}`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(`无法解析 JSON（HTTP ${res.status}）`);
  }
  if (!res.ok) {
    const detail =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : text.slice(0, 200);
    throw new Error(detail || `请求失败 ${res.status}`);
  }
  return data as T;
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8-8-8z"
        fill="currentColor"
      />
    </svg>
  );
}

function DryRunBlock({ data }: { data: DryRunResponse }) {
  const summary = data.summary ?? {};
  return (
    <div className="msg-body">
      <h2>dry-run 结果</h2>
      <p className="meta">
        review_task_count:{" "}
        {typeof summary.review_task_count === "number"
          ? String(summary.review_task_count)
          : String((data.review_tasks as unknown[]).length)}{" "}
        · chunk_count: {String(summary.chunk_count ?? "—")} · coarse_field_count:{" "}
        {String(summary.coarse_field_count ?? "—")}
        {typeof summary.trace_id === "string" ? (
          <>
            {" "}
            · trace <code>{summary.trace_id as string}</code>
          </>
        ) : null}
      </p>
      <p className="meta">
        <strong>field_extraction_task_counts</strong>：{fetCounts(summary)}
      </p>
      <p className="meta">
        <strong>source_library</strong>：{sourceLibraryOverview(summary)}
      </p>
      {Array.isArray(summary.markdown_line_records) &&
      (summary.markdown_line_records as unknown[]).length > 0 ? (
        <details className="dry-sub">
          <summary>markdown_line_records（前 20 条）</summary>
          <table className="dry-table">
            <thead>
              <tr>
                <th>pid</th>
                <th>category</th>
                <th>text_len</th>
              </tr>
            </thead>
            <tbody>
              {(
                summary.markdown_line_records as {
                  pid?: unknown;
                  category?: unknown;
                  text_len?: unknown;
                }[]
              )
                .slice(0, 20)
                .map((r, i) => (
                  <tr key={i}>
                    <td>{String(r.pid ?? "")}</td>
                    <td>{String(r.category ?? "")}</td>
                    <td>{String(r.text_len ?? "")}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </details>
      ) : null}
      <details className="dry-sub">
        <summary>field_extraction_tasks（最多 50 行）</summary>
        <p className="fet-cap-hint">共 {flattenFetRows(summary).length} 行</p>
        <table className="dry-table">
          <thead>
            <tr>
              <th>#</th>
              <th>摘要</th>
            </tr>
          </thead>
          <tbody>
            {flattenFetRows(summary)
              .slice(0, 50)
              .map((item) => (
                <tr key={item.key}>
                  <td className="fet-label">{item.label}</td>
                  <td>
                    <pre className="fet-pre">
                      {(() => {
                        const s = JSON.stringify(item.row);
                        return s.length > 2000 ? `${s.slice(0, 2000)}…` : s;
                      })()}
                    </pre>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
      <details className="dry-sub">
        <summary>summary JSON</summary>
        <pre className="md-pre">{JSON.stringify(summary, null, 2)}</pre>
      </details>
    </div>
  );
}

function ReviewBlock({ result }: { result: ReviewResponse }) {
  return (
    <div className="msg-body">
      <h2>审查完成</h2>
      <p className="meta">
        任务 {result.review_id} · {result.status}
        {typeof result.summary?.trace_id === "string" ? (
          <>
            {" "}
            · trace <code>{result.summary.trace_id as string}</code>
          </>
        ) : null}
      </p>
      {Array.isArray(result.summary?.error_collection) &&
      (result.summary.error_collection as unknown[]).length > 0 ? (
        <div className="warn-box">
          <strong>error_collection</strong>（共{" "}
          {(result.summary.error_collection as unknown[]).length} 条）
          <ul className="ec-list">
            {(result.summary.error_collection as ErrorCollectionRow[]).map((row, i) => (
              <li key={i} className="ec-li">
                <details className="ec-details">
                  <summary>
                    <span className="deg">{row.degree}</span> {row.source ?? "—"} · {row.title}
                  </summary>
                  <pre className="ec-comment">{row.comment}</pre>
                </details>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <h3>审查意见（{result.final_output.comment_list.length}）</h3>
      {result.final_output.comment_list.map((it, i) => (
        <div key={`${it.title}-${i}`} className="issue">
          <span className="deg">
            {it.degree} · category {it.category} · {it.item_type} / {it.action_type}
          </span>
          <h3>{it.title}</h3>
          <p>{it.comment}</p>
          {it.category === 1 && it.revised_text ? (
            <p style={{ marginTop: "0.5rem", fontSize: "0.88rem" }}>
              <strong>修订建议：</strong>
              {it.revised_text}
            </p>
          ) : null}
        </div>
      ))}
      {result.final_output.extracted_info.length > 0 ? (
        <>
          <h3>提取信息</h3>
          {result.final_output.extracted_info.map((it, i) => (
            <div key={`${it.title}-${i}`} className="issue">
              <h3>{it.title}</h3>
              <p>{it.comment}</p>
            </div>
          ))}
        </>
      ) : null}
      {result.markdown_report ? (
        <details className="dry-sub">
          <summary>Markdown 报告</summary>
          <pre className="md-pre">{result.markdown_report}</pre>
        </details>
      ) : null}
    </div>
  );
}

export default function App() {
  const [mode, setMode] = useState<"text" | "file">("text");
  const [rulesets, setRulesets] = useState<string[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [text, setText] = useState("");
  const [mainFile, setMainFile] = useState<File | null>(null);
  const [extraFiles, setExtraFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewResponse | null>(null);
  const [dryRunResult, setDryRunResult] = useState<DryRunResponse | null>(null);
  const [lastUserPreview, setLastUserPreview] = useState<string | null>(null);

  const [contractSubject, setContractSubject] = useState("");
  const [businessInfo, setBusinessInfo] = useState("");
  const [enterpriseList, setEnterpriseList] = useState("");
  const [includeFieldExtractionTasks, setIncludeFieldExtractionTasks] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const threadEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchJson<RulesetsResponse>("/rulesets")
      .then((r) => {
        setRulesets(r.ruleset_ids);
        const init: Record<string, boolean> = {};
        const ids = r.ruleset_ids;
        ids.forEach((id) => {
          init[id] = false;
        });
        if (ids.includes("demo")) init.demo = true;
        else if (ids.includes("base-rules")) init["base-rules"] = true;
        else if (ids.length) init[ids[0]] = true;
        setSelected(init);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [result, dryRunResult, loading, dryRunLoading, lastUserPreview, error]);

  const resizeComposer = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, []);

  useEffect(() => {
    resizeComposer();
  }, [text, mode, resizeComposer]);

  const selectedIds = useCallback(
    () => Object.entries(selected).filter(([, v]) => v).map(([k]) => k),
    [selected],
  );

  const buildTextJsonBody = useCallback((): Record<string, unknown> => {
    const ruleset_ids = selectedIds();
    const body: Record<string, unknown> = {
      text: text.trim(),
      ruleset_ids,
      user_position: "甲方",
    };
    const cs = contractSubject.trim();
    const bi = businessInfo.trim();
    const el = enterpriseList.trim();
    if (cs) body.contract_subject = cs;
    if (bi) body.business_info = bi;
    if (el) body.enterprise_list = el;
    if (includeFieldExtractionTasks) {
      body.include_field_extraction_tasks = true;
    }
    return body;
  }, [
    text,
    selectedIds,
    contractSubject,
    businessInfo,
    enterpriseList,
    includeFieldExtractionTasks,
  ]);

  const previewForUser = () => {
    if (mode === "text") {
      const t = text.trim();
      return t.length > 400 ? `${t.slice(0, 400)}…` : t;
    }
    const parts: string[] = [];
    if (mainFile) parts.push(`主文件：${mainFile.name}`);
    if (extraFiles?.length) parts.push(`附件 ${extraFiles.length} 个`);
    if (text.trim()) parts.push(text.trim().slice(0, 200));
    return parts.join("\n") || "（已选择上传，无补充文本）";
  };

  const runDryRun = async () => {
    if (mode !== "text") {
      setError("仅 dry-run 支持「粘贴文本」模式。");
      return;
    }
    setError(null);
    setResult(null);
    setDryRunResult(null);
    setLastUserPreview(previewForUser());
    setDryRunLoading(true);
    try {
      const body = { ...buildTextJsonBody() };
      delete body.include_field_extraction_tasks;
      const data = await fetchJson<DryRunResponse>("/reviews/dry-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setDryRunResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDryRunLoading(false);
    }
  };

  const runReview = async () => {
    setError(null);
    setResult(null);
    setDryRunResult(null);
    setLastUserPreview(previewForUser());
    setLoading(true);
    const ruleset_ids = selectedIds();
    try {
      if (mode === "text") {
        const data = await fetchJson<ReviewResponse>("/reviews", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildTextJsonBody()),
        });
        setResult(data);
      } else {
        const fd = new FormData();
        if (mainFile) fd.append("main_file", mainFile);
        if (extraFiles) {
          for (let i = 0; i < extraFiles.length; i++) {
            fd.append("attachments", extraFiles[i]);
          }
        }
        if (text.trim()) fd.append("text", text.trim());
        fd.append("ruleset_ids", JSON.stringify(ruleset_ids));
        fd.append("user_position", "甲方");
        if (contractSubject.trim()) fd.append("contract_subject", contractSubject.trim());
        if (businessInfo.trim()) fd.append("business_info", businessInfo.trim());
        if (enterpriseList.trim()) fd.append("enterprise_list", enterpriseList.trim());
        if (includeFieldExtractionTasks) {
          fd.append("include_field_extraction_tasks", "true");
        }
        const data = await fetchJson<ReviewResponse>("/reviews/upload", {
          method: "POST",
          body: fd,
        });
        setResult(data);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const canSubmit =
    selectedIds().length > 0 &&
    (mode === "text" ? text.trim().length > 0 : mainFile !== null || text.trim().length > 0);

  const canDryRunText = mode === "text" && selectedIds().length > 0 && text.trim().length > 0;

  const busy = loading || dryRunLoading;
  const showWelcome = !lastUserPreview && !busy && !result && !dryRunResult;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">合同审查</div>
        <div className="sidebar-section">
          <div className="sidebar-section-title">输入方式</div>
          <div className="seg">
            <button
              type="button"
              className={mode === "text" ? "active" : ""}
              onClick={() => setMode("text")}
            >
              粘贴文本
            </button>
            <button
              type="button"
              className={mode === "file" ? "active" : ""}
              onClick={() => setMode("file")}
            >
              上传文件
            </button>
          </div>
        </div>
        <div className="sidebar-section">
          <div className="sidebar-section-title">规则集</div>
          <div className="rules">
            {rulesets.length === 0 ? (
              <span className="meta" style={{ padding: "0 0.5rem" }}>
                加载中…
              </span>
            ) : (
              rulesets.map((id) => (
                <label key={id}>
                  <input
                    type="checkbox"
                    checked={!!selected[id]}
                    onChange={(e) =>
                      setSelected((s) => ({ ...s, [id]: e.target.checked }))
                    }
                  />
                  {id}
                </label>
              ))
            )}
          </div>
        </div>
        <details className="adv">
          <summary>高级选项</summary>
          <div className="adv-body">
            <p className="adv-hint">可选 Dify 入参：主体、工商、企业列表；可附带字段提取任务。</p>
            <label htmlFor="contract-subject">合同主体（src=1）</label>
            <textarea
              id="contract-subject"
              className="adv-ta"
              value={contractSubject}
              onChange={(e) => setContractSubject(e.target.value)}
            />
            <label htmlFor="business-info">工商信息（src=4）</label>
            <textarea
              id="business-info"
              className="adv-ta"
              value={businessInfo}
              onChange={(e) => setBusinessInfo(e.target.value)}
            />
            <label htmlFor="enterprise-list">企业列表（src=4）</label>
            <textarea
              id="enterprise-list"
              className="adv-ta"
              value={enterpriseList}
              onChange={(e) => setEnterpriseList(e.target.value)}
            />
            <label className="inline-check">
              <input
                type="checkbox"
                checked={includeFieldExtractionTasks}
                onChange={(e) => setIncludeFieldExtractionTasks(e.target.checked)}
              />
              附带 field_extraction_tasks
            </label>
          </div>
        </details>
        <p className="sidebar-hint">
          后端 <code>uvicorn … --port 8000</code>，本目录 <code>npm run dev</code>
        </p>
      </aside>

      <main className="main">
        <div className="thread">
          <div className="thread-inner">
            {showWelcome ? (
              <div className="welcome">
                <h1>合同要怎么审？</h1>
                <p>
                  在下方粘贴合同或上传文件，选择规则集后发送。我会按条款给出审查意见与风险提示，风格类似
                  ChatGPT 对话。
                </p>
              </div>
            ) : null}

            {lastUserPreview ? (
              <div className="msg">
                <div className="msg-avatar user">你</div>
                <div className="msg-body">
                  <p className="msg-preview">{lastUserPreview}</p>
                  <p className="meta" style={{ marginTop: "0.5rem" }}>
                    规则集：{selectedIds().join(", ") || "—"}
                  </p>
                </div>
              </div>
            ) : null}

            {busy ? (
              <div className="msg">
                <div className="msg-avatar assistant">审</div>
                <div className="msg-body">
                  <p className="loading-dots">
                    {loading ? "正在审查合同…" : "正在 dry-run…"}
                  </p>
                </div>
              </div>
            ) : null}

            {dryRunResult ? (
              <div className="msg">
                <div className="msg-avatar assistant">审</div>
                <DryRunBlock data={dryRunResult} />
              </div>
            ) : null}

            {result ? (
              <div className="msg">
                <div className="msg-avatar assistant">审</div>
                <ReviewBlock result={result} />
              </div>
            ) : null}

            <div ref={threadEndRef} />
          </div>
        </div>

        {error ? <div className="err-toast">{error}</div> : null}

        <div className="composer-wrap">
          <div className="composer">
            {mode === "file" ? (
              <div className="composer-file-row">
                <div>
                  <label htmlFor="main">主合同</label>
                  <input
                    id="main"
                    type="file"
                    accept=".txt,.md,.docx,.pdf"
                    onChange={(e) => setMainFile(e.target.files?.[0] ?? null)}
                  />
                </div>
                <div>
                  <label htmlFor="atts">附件</label>
                  <input
                    id="atts"
                    type="file"
                    multiple
                    accept=".txt,.md,.docx,.pdf"
                    onChange={(e) => setExtraFiles(e.target.files)}
                  />
                </div>
              </div>
            ) : null}
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onInput={resizeComposer}
              placeholder={
                mode === "text"
                  ? "粘贴合同全文，或输入要审查的内容…"
                  : "补充说明（可与上传文件一起提交）…"
              }
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && canSubmit && !busy) {
                  e.preventDefault();
                  void runReview();
                }
              }}
            />
            <div className="composer-actions">
              <div className="composer-actions-left">
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={busy || !canDryRunText}
                  onClick={() => void runDryRun()}
                >
                  dry-run
                </button>
              </div>
              <div className="composer-actions-right">
                <button
                  type="button"
                  className="btn-send"
                  disabled={busy || !canSubmit}
                  onClick={() => void runReview()}
                  title="开始审查（Enter）"
                  aria-label="开始审查"
                >
                  <SendIcon />
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
