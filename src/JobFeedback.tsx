import { useState } from "react";
import { Button } from "@fluentui/react-components";
import { DismissRegular } from "@fluentui/react-icons";
import { useTranslation } from "react-i18next";
import { type Job, size } from "./api";
import { IconButton } from "./Controls";
import { errorMessageKey, measuredSize, taskFailures, taskWarnings } from "./job-feedback";

export function JobFailures({ jobs, onJobs }: { jobs: Job[]; onJobs: () => void }) {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(new Set<string>());
  const [expanded, setExpanded] = useState(false);
  const failures = taskFailures(jobs).filter((failure) => !dismissed.has(failure.key));
  if (!failures.length) return null;
  return <div className="message error job-failures">
    <div role="alert">
      <strong>{t("batchFailures", { count: failures.length })}</strong>
      <ul>{(expanded ? failures : failures.slice(0, 10)).map(({ key, job, task }) =>
        <li key={key}><strong>{task.sources.join(", ")}</strong> · {t(`tool.${job.tool}`)}: {t(errorMessageKey(task.error) || "rawError", { defaultValue: task.error })}</li>
      )}</ul>
      {failures.length > 10 && !expanded && <Button appearance="subtle" onClick={() => setExpanded(true)}>{t("showAllFailures", { count: failures.length })}</Button>}
      <Button appearance="subtle" onClick={onJobs}>{t("jobs")}</Button>
    </div>
    <IconButton label={t("dismissErrors")} icon={<DismissRegular />} onClick={() => setDismissed((old) => new Set([...old, ...failures.map((failure) => failure.key)]))} />
  </div>;
}

export function JobWarnings({ jobs }: { jobs: Job[] }) {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(new Set<string>());
  const warnings = taskWarnings(jobs, dismissed);
  if (!warnings.length) return null;
  return <div className="message notice job-warnings" role="status">
    <details><summary>{t("batchWarnings", { count: warnings.length })}</summary>
      <ul>{warnings.map(warning => <li key={warning.key}><strong>{warning.source}</strong>: {t("imageWarning")} · {warning.message.replace(/^IMAGE_UNAVAILABLE: /, "")}</li>)}</ul>
    </details>
    <IconButton label={t("dismissWarnings")} icon={<DismissRegular />}
      onClick={() => setDismissed(old => new Set([...old, ...warnings.map(warning => warning.key)]))} />
  </div>;
}

export function OutputSizes({ job, stale }: { job?: Job; stale: boolean }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  if (!job || !["compress", "image"].includes(job.tool)) return null;
  const rows = expanded ? job.tasks : job.tasks.slice(0, 20);
  return <section className="output-sizes" aria-label={t("measuredSizes")}>
    <h3>{t("measuredSizes")}</h3>
    <p className="help">{t(stale ? "sizeResultsStale" : "sizeResultsMeasured")}</p>
    <div className="output-size-rows">{rows.map((task) => {
      const result = measuredSize(task);
      return <article key={task.index}>
        <strong className="filename">{task.sources.join(", ")}</strong>
        {task.error ? <p className="task-error">{t(errorMessageKey(task.error) || "rawError", { defaultValue: task.error })}</p> : result ? <>
          <p>{t("before")}: {size(result.input)} → {t("after")}: {size(result.output)}{result.change !== null && ` (${result.change > 0 ? "+" : ""}${result.change.toFixed(1)}%)`}</p>
          <details><summary>{t("outputFiles", { count: result.outputs.length })}</summary>
            <ul>{result.outputs.map((output, index) => <li key={output.id || index}>{output.name} · {size(output.size)}</li>)}</ul>
          </details>
        </> : <p>{t(task.state)}</p>}
      </article>;
    })}</div>
    {job.tasks.length > 20 && !expanded && <Button appearance="subtle" onClick={() => setExpanded(true)}>{t("showAllResults", { count: job.tasks.length })}</Button>}
  </section>;
}
