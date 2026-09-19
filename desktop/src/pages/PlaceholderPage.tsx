/**
 * Navigation targets whose data model arrives in a later milestone.
 *
 * These say plainly what is missing and when it lands. They deliberately show
 * no mocked orders, customers or figures: a screen of invented data is worse
 * than an honest empty one, because it looks like it works.
 */
import { Panel } from '../components/ui';

interface PlaceholderPageProps {
  title: string;
  milestone: string;
  summary: string;
  planned: string[];
}

export function PlaceholderPage({ title, milestone, summary, planned }: PlaceholderPageProps) {
  return (
    <Panel>
      <div className="px-6 py-10" data-testid="placeholder-page">
        <div className="mx-auto max-w-xl text-center">
          <span className="inline-flex items-center rounded-full bg-shell-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-shell-600">
            Arrives in {milestone}
          </span>
          <h2 className="mt-4 text-xl font-semibold text-shell-900">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-shell-600">{summary}</p>

          <ul className="mx-auto mt-6 max-w-sm space-y-2 text-left">
            {planned.map((line) => (
              <li key={line} className="flex items-start gap-2.5 text-sm text-shell-600">
                <svg viewBox="0 0 20 20" fill="currentColor" className="mt-0.5 h-4 w-4 shrink-0 text-shell-400">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-13a.75.75 0 01.75.75v5.5a.75.75 0 01-1.5 0v-5.5A.75.75 0 0110 5z" clipRule="evenodd" />
                </svg>
                {line}
              </li>
            ))}
          </ul>

          <p className="mt-8 text-xs text-shell-400">
            No sample data is shown here on purpose — every figure in this console
            comes from the live database.
          </p>
        </div>
      </div>
    </Panel>
  );
}
