import { validateInput, type ExpenseInput, type RunResult, type RunService } from '../workflow'

const mockResult: RunResult = {
    runId: 'demo-run',
    completedAt: '2026-10-09T12:00:00.000Z',
    input: { date: '2026-10-09', description: 'Mercado demonstrativo', amountCents: 12345, category: 'Alimentacao', payment: 'debito', recurring: false },
    month: '2026-10',
    totalCents: 12345,
    count: 1,
    recurringCents: 0,
    categories: [{ name: 'Alimentacao', cents: 12345 }],
    payments: [{ name: 'debito', cents: 12345 }],
}

export function createRunService(latency = 1200): RunService {
    let readyAt: number | null = null

    return {
        async startRun(rawInput: ExpenseInput) {
            validateInput(rawInput)
            readyAt = Date.now() + latency
            return { runId: mockResult.runId }
        },
        async getRunStatus(runId: string) {
            if (runId !== mockResult.runId || readyAt === null) throw new Error('Execucao nao encontrada. Tente novamente.')
            if (Date.now() < readyAt) return { status: 'running' }
            return { status: 'done', result: structuredClone(mockResult) }
        },
    }
}

const demoService = createRunService()
export const startRun = demoService.startRun
export const getRunStatus = demoService.getRunStatus