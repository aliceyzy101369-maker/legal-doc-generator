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
  final_output: {
    comment_list: FinalItem[];
    extracted_info: { title: string; comment: string }[];
  };
};

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
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReviewResponse | null>(null);

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

  const runReview = async () => {
    setError(null);
    setResult(null);
    setLoading(true);
    const ruleset_ids = selectedIds();
    try {
      if (mode === "text") {
        const body = {
          text: text.trim(),
          ruleset_ids,
          user_position: "甲方",
        };
        const data = await fetchJson<ReviewResponse>("/reviews", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
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

        <button
          type="button"
          className="primary"
          disabled={loading || !canSubmit}
          onClick={() => void runReview()}
        >
          {loading ? "审查中…" : "开始审查"}
        </button>
        {error ? <div className="err">{error}</div> : null}
      </div>

      {result ? (
        <div className="panel">
          <div className="meta">
            任务 {result.review_id} · {result.status}
          </div>
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
        </div>
      ) : null}
    </div>
  );
}
