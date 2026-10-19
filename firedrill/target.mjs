import { fileURLToPath } from 'node:url';
import { resolve, join } from 'node:path';
import { ApplicationError, commandMain, invokeCLI, privateDirectory } from './adapter-runtime.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const cases = new Set(["original-five", "replacement", "partial-refund", "busy-operations", "conflicting-request", "unfunded-refund", "unconfirmed-loss", "hostile-request", "fully-refunded-stock", "one-cent-remaining", "maximum-safe-cents", "address-before-shipment"]);
export async function runApplication(input, parameters, signal, invocation) {
  const validModel = value => typeof value === 'string' && /^(openai|anthropic|google):[A-Za-z0-9._-]{1,160}$/.test(value);
  if (Object.keys(input).some(key => !['caseId', 'action', 'models', 'maxRuns', 'maxProviderRequests'].includes(key)) || !cases.has(input.caseId) || !['compare', 'plan', 'inspect'].includes(input.action) ||
      !Array.isArray(input.models) || input.models.length < 1 || input.models.length > 3 || !input.models.every(validModel) ||
      !Number.isSafeInteger(input.maxRuns) || input.maxRuns < 1 || input.maxRuns > 128 || !Number.isSafeInteger(input.maxProviderRequests) || input.maxProviderRequests < 1 || input.maxProviderRequests > 768 ||
      (parameters.model !== undefined && !validModel(parameters.model))) throw new Error('Supply a reviewed study, explicit model identifiers and independent bounded execution/provider-attempt ceilings.');
  const directory = await privateDirectory(root, invocation), workspace = join(directory, 'workspace');
  const cli = ['uv', 'run', '--locked', '--no-sync', 'compare-orders'];
  try {
    const initialized = await invokeCLI([...cli, 'init', '--directory', workspace, '--case', input.caseId], { cwd: root, signal });
    for (const key of ['cases', 'expectations']) if (typeof initialized[key] !== 'string' || !initialized[key].startsWith(workspace + '/')) throw new Error('Initialized study/oracle path is outside its owned workspace.');
    const models = parameters.model ? [parameters.model] : input.models;
    const argv = input.action === 'inspect' ? [...cli, 'workspace', workspace] : [...cli, '--cases', initialized.cases, '--expectations', initialized.expectations, ...models.flatMap(model => ['--model', model]), '--output-root', join(directory, 'receipts'), '--output', join(directory, 'report.json'), '--timeout-seconds', '180'];
    if (input.action === 'compare') argv.push('--live', '--max-runs', String(input.maxRuns), '--max-provider-requests', String(input.maxProviderRequests));
    return { executionKind: input.action === 'inspect' ? 'application_state_inspection' : input.action === 'plan' ? 'application_dry_plan' : 'native_model_comparison', application: await invokeCLI(argv, { cwd: root, signal, timeoutMs: 210000 }), localState: { directory, workspaceRoot: workspace } };
  } catch (error) { if (error instanceof ApplicationError) error.evidence.runDirectory = directory; throw error; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await commandMain(runApplication);
