import { categories, payments, validateInput, type ExpenseInput, type RunResult, type RunService } from '../workflow'

export function createRunService(latency = 1200): RunService {
    const runs = new Map<string, { readyAt: number; result: RunResult; completed: boolean }>()

    return {
        async startRun(rawInput: ExpenseInput) {
            const input = validateInput(rawInput)
            const runId = crypto.randomUUID()
            const month = input.date.slice(0, 7)
            const entries = [...runs.values()]
                .filter(run => run.completed && run.result.month === month)
                .map(run => run.result.input)
            entries.push(input)
            const sum = (expenses: ExpenseInput[]) => expenses.reduce((total, expense) => total + expense.amountCents, 0)
            const readyAt = Date.now() + latency
            const result: RunResult = {
                runId, input, month, completedAt: new Date(readyAt).toISOString(),
                totalCents: sum(entries), count: entries.length,
                recurringCents: sum(entries.filter(expense => expense.recurring)),
                categories: categories.map(name => ({ name, cents: sum(entries.filter(expense => expense.category === name)) })).filter(item => item.cents > 0),
                payments: (Object.keys(payments) as (keyof typeof payments)[]).map(name => ({ name, cents: sum(entries.filter(expense => expense.payment === name)) })).filter(item => item.cents > 0),
            }
            runs.set(runId, { readyAt, result, completed: false })
            return { runId }
        },
        async getRunStatus(runId: string) {
            const run = runs.get(runId)
            if (!run) throw new Error('Execucao nao encontrada. Tente novamente.')
            if (Date.now() < run.readyAt) return { status: 'running' }
            run.completed = true
            return { status: 'done', result: structuredClone(run.result) }
        },
    }
}

const demoService = createRunService()
export const startRun = demoService.startRun
export const getRunStatus = demoService.getRunStatus