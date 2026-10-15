type ApiEnvelope<T> = {
    data: T | null
    errors: { code: string; message: string }[]
    meta: { request_id: string; schema_version: string }
}

export type HouseholdCategory = {
    id: string
    label: string
    parent_category_id: string | null
    is_active: boolean
    is_standard: boolean
}

export type HouseholdExpense = {
    id: string
    date: string
    description: string
    amount_cents: number
    payment_method: string
    recurring: boolean
    category_id: string
    source: string
    confidence: number | null
    review_required: boolean
    user_override: boolean
}

export type ImportRun = {
    id: string
    total_rows: number
    imported_rows: number
    rejected_rows: number
    row_errors: { row: number; field: string; code: string; message: string; value: string | null }[]
    status: string
}

export type EvaluationReport = {
    total_count: number
    correct_count: number
    accuracy: number
    passed: boolean
    confusion_details: { expected_category_id: string; predicted_category_id: string; count: number }[]
}

export type HouseholdService = {
    listCategories(): Promise<HouseholdCategory[]>
    listExpenses(filters: {
        month: string
        categoryId?: string
        confidenceMin?: number
        paymentMethod?: string
        source?: string
        reviewRequired?: boolean
        offset?: number
    }): Promise<{ expenses: HouseholdExpense[]; totalCount: number }>
    importCsv(file: File): Promise<ImportRun>
    correctCategory(expenseId: string, categoryId: string): Promise<HouseholdExpense>
    createCategory(label: string, parentCategoryId: string): Promise<HouseholdCategory>
    renameCategory(categoryId: string, label: string): Promise<HouseholdCategory>
    mergeCategories(sourceCategoryId: string, targetCategoryId: string): Promise<HouseholdCategory>
    exportCsv(): Promise<Blob>
    exportArchive(): Promise<Blob>
    getDemoHouseholdId(): Promise<string>
    deleteDemoData(householdId: string): Promise<void>
    evaluate(): Promise<EvaluationReport>
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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

async function download(path: string): Promise<Blob> {
    let response: Response
    try {
        response = await fetch(`${baseUrl}${path}`, { headers: { Accept: '*/*' } })
    } catch {
        throw new Error('Backend indisponível. Inicie a API local e tente novamente.')
    }
    if (!response.ok) {
        const envelope = await response.json() as ApiEnvelope<unknown>
        throw new Error(envelope.errors[0]?.message ?? 'Não foi possível exportar os dados.')
    }
    return response.blob()
}

export const householdService: HouseholdService = {
    async listCategories() {
        const data = await request<{ categories: HouseholdCategory[] }>('/categories')
        return data.categories
    },
    async listExpenses({ month, categoryId, confidenceMin, paymentMethod, source, reviewRequired, offset = 0 }) {
        const params = new URLSearchParams({ month, limit: '100', offset: String(offset) })
        if (categoryId) params.set('category_id', categoryId)
        if (confidenceMin !== undefined) params.set('confidence_min', String(confidenceMin))
        if (paymentMethod) params.set('payment_method', paymentMethod)
        if (source) params.set('source', source)
        if (reviewRequired !== undefined) params.set('review_required', String(reviewRequired))
        const data = await request<{ expenses: HouseholdExpense[]; total_count: number }>(`/expenses?${params}`)
        return { expenses: data.expenses, totalCount: data.total_count }
    },
    async importCsv(file) {
        const data = await request<{ import_run: ImportRun }>(`/imports/csv?source_name=${encodeURIComponent(file.name)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'text/csv' },
            body: await file.text(),
        })
        return data.import_run
    },
    async correctCategory(expenseId, categoryId) {
        const data = await request<{ expense: HouseholdExpense }>(`/expenses/${encodeURIComponent(expenseId)}/category`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category_id: categoryId }),
        })
        return data.expense
    },
    async createCategory(label, parentCategoryId) {
        const data = await request<{ category: HouseholdCategory }>('/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label, parent_category_id: parentCategoryId }),
        })
        return data.category
    },
    async renameCategory(categoryId, label) {
        const data = await request<{ category: HouseholdCategory }>(`/categories/${encodeURIComponent(categoryId)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ label }),
        })
        return data.category
    },
    async mergeCategories(sourceCategoryId, targetCategoryId) {
        const data = await request<{ category: HouseholdCategory }>('/categories/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_category_id: sourceCategoryId, target_category_id: targetCategoryId }),
        })
        return data.category
    },
    exportCsv: () => download('/exports/expenses.csv'),
    async exportArchive() {
        const data = await request<{ archive: unknown }>('/exports/archive.json')
        return new Blob([JSON.stringify(data.archive, null, 2)], { type: 'application/json' })
    },
    async getDemoHouseholdId() {
        const data = await request<{ household: { id: string } }>('/households/demo')
        return data.household.id
    },
    async deleteDemoData(householdId) {
        await request(`/households/${encodeURIComponent(householdId)}/demo-data`, { method: 'DELETE' })
    },
    async evaluate() {
        const data = await request<{ evaluation: EvaluationReport }>('/evaluation/categorization', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        })
        return data.evaluation
    },
}