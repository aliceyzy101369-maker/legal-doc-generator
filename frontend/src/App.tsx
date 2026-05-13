import { useCallback, useEffect, useState } from "react";

type RulesetsResponse = { ruleset_ids: string[] };

type FinalItem = {
  title: string;
  comment: string;
  degree: string;
  category: number;
  change_type?: string;
  revised_text?: string;
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
    | { mode_1?: unknown[]; mode_23?: unknown[] }
    | undefined;
  if (!fet) return [];
  const rows: { key: string; label: string; row: Record<string, unknown> }[] = [];
  (Array.isArray(fet.mode_1) ? fet.mode_1 : []).forEach((r, i) => {
    rows.push({
      key: `m1-${i}`,
      label: `mode_1 #${i + 1}`,
      row: typeof r === "object" && r !== null ? (r as Record<string, unknown>) : {},
    });
  });
  (Array.isArray(fet.mode_23) ? fet.mode_23 : []).forEach((r, i) => {
    rows.push({
      key: `m23-${i}`,
      label: `mode_23 #${i + 1}`,
      row: typeof r === "object" && r !== null ? (r as Record<string, unknown>) : {},
    });
  });
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

  const [contractSubject, setContractSubject] = useState("");
  const [businessInfo, setBusinessInfo] = useState("");
  const [enterpriseList, setEnterpriseList] = useState("");
  const [includeFieldExtractionTasks, setIncludeFieldExtractionTasks] =
    useState(false);

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

  const runDryRun = async () => {
    if (mode !== "text") {
      setError("仅 dry-run 仅支持「粘贴文本」模式。");
      return;
    }
    setError(null);
    setResult(null);
    setDryRunResult(null);
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
        if (contractSubject.trim()) {
          fd.append("contract_subject", contractSubject.trim());
        }
        if (businessInfo.trim()) {
          fd.append("business_info", businessInfo.trim());
        }
        if (enterpriseList.trim()) {
          fd.append("enterprise_list", enterpriseList.trim());
        }
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
    (mode === "text"
      ? text.trim().length > 0
      : mainFile !== null || text.trim().length > 0);

  const canDryRunText =
    mode === "text" &&
    selectedIds().length > 0 &&
    text.trim().length > 0;

  return (
    <div className="app">
      <h1>合同审查</h1>
      <p className="sub">
        对接本仓库 FastAPI：先启动后端{" "}
        <code>uvicorn contract_review_api.main:app --reload --port 8000</code>
        ，再在本目录执行 <code>npm run dev</code>。
      </p>

      <div className="panel">
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

        <label>规则集</label>
        <div className="rules">
          {rulesets.length === 0 ? (
            <span className="meta">加载中…</span>
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

        {mode === "text" ? (
          <>
            <label htmlFor="contract-text">合同正文</label>
            <textarea
              id="contract-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="粘贴合同全文…"
            />
          </>
        ) : (
          <>
            <div className="row">
              <div>
                <label htmlFor="main">主合同（.txt / .md / .docx / .pdf）</label>
                <input
                  id="main"
                  type="file"
                  accept=".txt,.md,.docx,.pdf"
                  onChange={(e) => setMainFile(e.target.files?.[0] ?? null)}
                />
              </div>
              <div>
                <label htmlFor="atts">附件（可选，多选）</label>
                <input
                  id="atts"
                  type="file"
                  multiple
                  accept=".txt,.md,.docx,.pdf"
                  onChange={(e) => setExtraFiles(e.target.files)}
                />
              </div>
            </div>
            <label htmlFor="extra-text">补充说明文本（可选，与文件合并）</label>
            <textarea
              id="extra-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="可与上传文件一起提交…"
            />
          </>
        )}

        <details className="adv">
          <summary>高级选项（对齐 Dify 入参 / 可观测）</summary>
          <p className="adv-hint">
            可选：写入来源库 src=1 / src=4；勾选后在{" "}
            <code>summary</code> 中附带 §5.1 字段提取任务列表（响应会变大）。
          </p>
          <label htmlFor="contract-subject">合同主体补充（src=1）</label>
          <textarea
            id="contract-subject"
            className="adv-ta"
            value={contractSubject}
            onChange={(e) => setContractSubject(e.target.value)}
            placeholder="例如：法定代表人、注册地址等（可选）"
          />
          <label htmlFor="business-info">工商信息（src=4）</label>
          <textarea
            id="business-info"
            className="adv-ta"
            value={businessInfo}
            onChange={(e) => setBusinessInfo(e.target.value)}
            placeholder="统一社会信用代码等（可选）"
          />
          <label htmlFor="enterprise-list">企业列表（src=4，可与工商合并）</label>
          <textarea
            id="enterprise-list"
            className="adv-ta"
            value={enterpriseList}
            onChange={(e) => setEnterpriseList(e.target.value)}
            placeholder='JSON 数组或纯文本（可选），如 [{"name":"子公司"}]'
          />
          <label className="inline-check">
            <input
              type="checkbox"
              checked={includeFieldExtractionTasks}
              onChange={(e) =>
                setIncludeFieldExtractionTasks(e.target.checked)
              }
            />
            在审查结果中附带 §5.1 <code>field_extraction_tasks</code>
          </label>
        </details>

        <div className="btn-row">
          <button
            type="button"
            className="primary"
            disabled={loading || dryRunLoading || !canSubmit}
            onClick={() => void runReview()}
          >
            {loading ? "审查中…" : "开始审查"}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={loading || dryRunLoading || !canDryRunText}
            onClick={() => void runDryRun()}
            title="POST /reviews/dry-run：不落库，返回任务与 summary"
          >
            {dryRunLoading ? "dry-run 中…" : "仅 dry-run"}
          </button>
        </div>
        {error ? <div className="err">{error}</div> : null}
      </div>

      {dryRunResult ? (
        <div className="panel dry-run-panel">
          <h2 className="h2-sm">dry-run（未跑完整审查 LLM）</h2>
          <div className="meta">
            review_task_count:{" "}
            {typeof dryRunResult.summary?.review_task_count === "number"
              ? String(dryRunResult.summary.review_task_count)
              : String((dryRunResult.review_tasks as unknown[]).length)}{" "}
            · review_tasks 数组: {(dryRunResult.review_tasks as unknown[]).length}{" "}
            条 · chunk_count:{" "}
            {String(dryRunResult.summary?.chunk_count ?? "—")} ·
            coarse_field_count:{" "}
            {String(dryRunResult.summary?.coarse_field_count ?? "—")}
            {typeof dryRunResult.summary?.trace_id === "string" ? (
              <>
                {" "}
                · trace <code>{dryRunResult.summary.trace_id as string}</code>
              </>
            ) : null}
          </div>
          <p className="meta dry-meta-block">
            <strong>field_extraction_task_counts</strong>：mode_1={" "}
            {String(
              (dryRunResult.summary?.field_extraction_task_counts as Record<string, unknown> | undefined)?.mode_1 ??
                "—",
            )}
            ，mode_23={" "}
            {String(
              (dryRunResult.summary?.field_extraction_task_counts as Record<string, unknown> | undefined)?.mode_23 ??
                "—",
            )}
          </p>
          <p className="meta dry-meta-block">
            <strong>source_library</strong> 长度概览：{sourceLibraryOverview(dryRunResult.summary ?? {})}
          </p>
          {Array.isArray(dryRunResult.summary?.markdown_line_records) &&
          (dryRunResult.summary.markdown_line_records as unknown[]).length > 0 ? (
            <details className="dry-sub">
              <summary>
                markdown_line_records（前 20 条，无正文）
              </summary>
              <table className="dry-table">
                <thead>
                  <tr>
                    <th>pid</th>
                    <th>category</th>
                    <th>text_len</th>
                  </tr>
                </thead>
                <tbody>
                  {(dryRunResult.summary.markdown_line_records as { pid?: unknown; category?: unknown; text_len?: unknown }[])
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
            <summary>
              field_extraction_tasks（最多展示 50 行，避免卡顿）
            </summary>
            <div className="fet-cap-hint">共 {flattenFetRows(dryRunResult.summary ?? {}).length} 行，仅渲染前 50 行。</div>
            <table className="dry-table fet-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>摘要（JSON 节选）</th>
                </tr>
              </thead>
              <tbody>
                {flattenFetRows(dryRunResult.summary ?? {})
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
          <details>
            <summary>summary JSON（可折叠）</summary>
            <pre className="md-pre">
              {JSON.stringify(dryRunResult.summary, null, 2)}
            </pre>
          </details>
        </div>
      ) : null}

      {result ? (
        <div className="panel">
          <div className="meta">
            任务 {result.review_id} · {result.status}
            {typeof result.summary?.trace_id === "string" ? (
              <>
                {" "}
                · trace <code>{result.summary.trace_id as string}</code>
              </>
            ) : null}
          </div>
          {Array.isArray(result.summary?.error_collection) &&
          (result.summary.error_collection as unknown[]).length > 0 ? (
            <div className="warn-box">
              <strong>error_collection</strong>（基础设施降级，共{" "}
              {(result.summary.error_collection as unknown[]).length} 条）
              <ul className="ec-list">
                {(result.summary.error_collection as ErrorCollectionRow[]).map((row, i) => (
                  <li key={i} className="ec-li">
                    <details className="ec-details">
                      <summary className="ec-sum">
                        <span className="deg">{row.degree}</span>{" "}
                        <span className="ec-src">{row.source ?? "—"}</span>{" "}
                        {row.title}
                      </summary>
                      <pre className="ec-comment">{row.comment}</pre>
                    </details>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <h2 style={{ fontSize: "1.1rem", margin: "0 0 0.75rem" }}>审查意见</h2>
          {result.final_output.comment_list.map((it, i) => (
            <div key={`${it.title}-${i}`} className="issue">
              <span className="deg">
                {it.degree} · category {it.category}
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
          <h2 style={{ fontSize: "1.1rem", margin: "1.25rem 0 0.5rem" }}>
            提取信息
          </h2>
          {result.final_output.extracted_info.map((it, i) => (
            <div key={`${it.title}-${i}`} className="issue">
              <h3>{it.title}</h3>
              <p>{it.comment}</p>
            </div>
          ))}
          {result.markdown_report ? (
            <>
              <h2 style={{ fontSize: "1.1rem", margin: "1.25rem 0 0.5rem" }}>
                Markdown 报告
              </h2>
              <details>
                <summary>展开查看</summary>
                <pre className="md-pre">{result.markdown_report}</pre>
              </details>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
