import {
    categoryOptions,
    payments,
    validateInput,
    type CategoryOption,
    type ExpenseInput,
    type RunResult,
    type RunService,
} from '../workflow'

type ApiEnvelope<T> = {
    data: T | null
    errors: { code: string; message: string }[]
    meta: { request_id: string; schema_version: string }
}

type ExpenseRecord = {
    id: string
    date: string
    description: string
    amount_cents: number
    payment_method: keyof typeof payments
    recurring: boolean
    category_id: string
    created_at: string
}

type MonthlyDashboard = {
    month: string
    total_cents: number
    expense_count: number
    recurring_cents: number
    category_breakdown: { category_id: string; label: string; amount_cents: number }[]
    payment_breakdown: { payment_method: keyof typeof payments; amount_cents: number }[]
}

type CategoryRecord = {
    id: string
    label: string
    parent_category_id: string | null
    is_active: boolean
}

type MonthlyInsightResponse = {
    insight_run: {
        cards: { title: string; text: string; source_refs: string[] }[]
    }
    sources: Record<string, {
        expense_id: string
        category_label: string
        date: string
        amount_cents: number
    }[]>
}

const mockResult: RunResult = {
    runId: 'demo-run',
    completedAt: '2026-10-09T12:00:00.000Z',
    input: { date: '2026-10-09', description: 'Mercado demonstrativo', amountCents: 12345, category: 'category-mercado', payment: 'debito', recurring: false },
    month: '2026-10',
    totalCents: 12345,
    count: 1,
    recurringCents: 0,
    categories: [{ name: 'category-mercado', label: 'Mercado', cents: 12345 }],
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

async function request<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
    let response: Response
    try {
        response = await fetch(`${baseUrl}${path}`, {
            ...init,
            headers: { Accept: 'application/json', ...init?.headers },
        })
    } catch {
        throw new Error('Backend indisponível. Inicie a API local e tente novamente.')
    }

    const envelope = await response.json() as ApiEnvelope<T>
    if (!response.ok || envelope.errors.length > 0 || envelope.data === null) {
        throw new Error(envelope.errors[0]?.message ?? 'Não foi possível concluir a operação.')
    }
    return envelope.data
}

export function createApiRunService(
    baseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, ''),
): RunService {
    const results = new Map<string, RunResult>()
    const pendingExpenses = new Map<string, ExpenseRecord>()
    let allowedCategoryIds: string[] = categoryOptions.map(option => option.id)

    async function getCategories(): Promise<CategoryOption[]> {
        const data = await request<{ categories: CategoryRecord[] }>(baseUrl, '/categories')
        const parentIds = new Set(
            data.categories.flatMap(category => category.parent_category_id ?? []),
        )
        const activeLeaves = data.categories
            .filter(category => category.is_active && !parentIds.has(category.id))
            .map(({ id, label }) => ({ id, label }))
        allowedCategoryIds = activeLeaves.map(category => category.id)
        return activeLeaves
    }

    async function startRun(rawInput: ExpenseInput, requestId = crypto.randomUUID()): Promise<{ runId: string }> {
        const input = validateInput(rawInput, allowedCategoryIds)
        let expense = pendingExpenses.get(requestId)
        if (!expense) {
            const createdData = await request<{ expense: ExpenseRecord }>(baseUrl, '/expenses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    date: input.date,
                    description: input.description,
                    amount_cents: input.amountCents,
                    payment_method: input.payment,
                    category_id: input.category,
                    recurring: input.recurring,
                }),
            })
            expense = createdData.expense
            pendingExpenses.set(requestId, expense)
        }
        const month = expense.date.slice(0, 7)
        const dashboardData = await request<{ dashboard: MonthlyDashboard }>(
            baseUrl,
            `/dashboard/monthly?month=${encodeURIComponent(month)}`,
        )
        const dashboard = dashboardData.dashboard
        let insight: RunResult['insight']
        try {
            const insightData = await request<MonthlyInsightResponse>(baseUrl, '/insights/monthly', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ month }),
            })
            const card = insightData.insight_run.cards[0]
            if (card) {
                insight = {
                    title: card.title,
                    text: card.text,
                    sources: card.source_refs.flatMap(token => insightData.sources[token] ?? []).map(source => ({
                        expenseId: source.expense_id,
                        categoryLabel: source.category_label,
                        date: source.date,
                        amountCents: source.amount_cents,
                    })),
                }
            }
        } catch {
            // Insights are best-effort; a failure must not turn a persisted expense into a failed run.
        }
        results.set(expense.id, {
            runId: expense.id,
            completedAt: expense.created_at,
            input,
            month: dashboard.month,
            totalCents: dashboard.total_cents,
            count: dashboard.expense_count,
            recurringCents: dashboard.recurring_cents,
            categories: dashboard.category_breakdown.map(item => ({
                name: item.category_id,
                label: item.label,
                cents: item.amount_cents,
            })),
            payments: dashboard.payment_breakdown.map(item => ({
                name: item.payment_method,
                cents: item.amount_cents,
            })),
            insight,
        })
        pendingExpenses.delete(requestId)
        return { runId: expense.id }
    }

    async function getRunStatus(runId: string) {
        const result = results.get(runId)
        if (!result) throw new Error('Execução não encontrada. Tente novamente.')
        return { status: 'done' as const, result: structuredClone(result) }
    }

    return { startRun, getRunStatus, getCategories }
}

const apiService = createApiRunService()
export const startRun = apiService.startRun
export const getRunStatus = apiService.getRunStatus
export const getCategories = apiService.getCategories