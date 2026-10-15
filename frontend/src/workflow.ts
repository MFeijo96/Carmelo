export const categoryOptions = [
    { id: 'category-moradia', label: 'Moradia' },
    { id: 'category-mercado', label: 'Mercado' },
    { id: 'category-restaurantes', label: 'Restaurantes' },
    { id: 'category-transporte', label: 'Transporte' },
    { id: 'category-saude', label: 'Saúde' },
    { id: 'category-educacao', label: 'Educação' },
    { id: 'category-contas-da-casa', label: 'Contas da casa' },
    { id: 'category-assinaturas', label: 'Assinaturas' },
    { id: 'category-dividas', label: 'Dívidas' },
    { id: 'category-pets', label: 'Pets' },
    { id: 'category-impostos-taxas', label: 'Impostos/taxas' },
    { id: 'category-cuidados-pessoais', label: 'Cuidados pessoais' },
    { id: 'category-outros', label: 'Outros' },
] as const
export const categories = categoryOptions.map(option => option.id)
export const payments = { dinheiro: 'Dinheiro', debito: 'Debito', credito: 'Credito' } as const

export type Category = string
export type CategoryOption = { id: string; label: string }
export type Payment = keyof typeof payments
export type ExpenseInput = {
    date: string
    description: string
    amountCents: number
    category: Category
    payment: Payment
    recurring: boolean
}
export type InsightSource = {
    expenseId: string
    categoryLabel: string
    date: string
    amountCents: number
}
export type RunResult = {
    runId: string
    completedAt: string
    input: ExpenseInput
    month: string
    totalCents: number
    count: number
    recurringCents: number
    categories: { name: Category; label: string; cents: number }[]
    payments: { name: Payment; cents: number }[]
    insight?: { title: string; text: string; sources: InsightSource[] }
}
export type RunStatus = { status: 'running' } | { status: 'done'; result: RunResult }
export type RunService = {
    startRun(input: ExpenseInput, requestId?: string): Promise<{ runId: string }>
    getRunStatus(runId: string): Promise<RunStatus>
    getCategories?(): Promise<CategoryOption[]>
}
export type CompletedRun = RunResult & { requestId: string; submittedInput: ExpenseInput }
export type WorkflowState = {
    phase: 'idle' | 'running' | 'done'
    runId: string | null
    history: CompletedRun[]
    error: string | null
}
export type WorkflowEvent =
    | { type: 'started'; runId: string }
    | { type: 'completed'; runId: string; result: RunResult; input: ExpenseInput }
    | { type: 'failed'; runId: string; message: string }
    | { type: 'cleared' }
    | { type: 'reset' }

export const initialState: WorkflowState = { phase: 'idle', runId: null, history: [], error: null }

export function workflowReducer(state: WorkflowState, event: WorkflowEvent): WorkflowState {
    switch (event.type) {
        case 'cleared':
            return initialState
        case 'started':
            return state.phase === 'running' ? state : { ...state, phase: 'running', runId: event.runId, error: null }
        case 'completed':
            if (state.phase !== 'running' || state.runId !== event.runId) return state
            return { phase: 'done', runId: null, error: null, history: [{ ...event.result, requestId: event.runId, submittedInput: { ...event.input } }, ...state.history] }
        case 'failed':
            if (state.phase !== 'running' || state.runId !== event.runId) return state
            return { ...state, phase: 'idle', runId: null, error: event.message }
        case 'reset':
            return state.phase === 'running' ? state : { ...state, phase: 'idle', error: null }
    }
}

export function parseAmount(value: string): number {
    const trimmed = value.trim()
    if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(trimmed)) {
        throw new Error('Informe um valor em reais, como 123,45.')
    }
    const [whole, fraction = ''] = trimmed.replaceAll('.', '').split(',')
    const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
    if (!Number.isSafeInteger(cents) || cents <= 0 || cents > 99_999_999) {
        throw new Error('O valor deve estar entre R$ 0,01 e R$ 999.999,99.')
    }
    return cents
}

export function validateInput(input: ExpenseInput, allowedCategories: readonly string[] = categories): ExpenseInput {
    const date = new Date(`${input.date}T12:00:00Z`)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(input.date) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== input.date) {
        throw new Error('Informe uma data valida.')
    }
    const description = input.description.trim()
    if (!description || description.length > 120) throw new Error('Informe uma descricao de ate 120 caracteres.')
    if (!Number.isSafeInteger(input.amountCents) || input.amountCents <= 0 || input.amountCents > 99_999_999) {
        throw new Error('Informe um valor positivo em reais.')
    }
    if (!allowedCategories.includes(input.category) || !Object.hasOwn(payments, input.payment) || typeof input.recurring !== 'boolean') {
        throw new Error('Confira categoria, pagamento e recorrencia.')
    }
    return { ...input, description }
}

export const money = (cents: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(cents / 100)
export const monthLabel = (month: string) => new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${month}-01T12:00:00Z`))