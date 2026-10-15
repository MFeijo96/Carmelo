import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApiRunService } from './runs'
import type { ExpenseInput } from '../workflow'

afterEach(() => vi.unstubAllGlobals())

const envelope = <T,>(data: T, errors: { code: string; message: string }[] = []) => ({
    data,
    errors,
    meta: { request_id: 'test-request', schema_version: '1.0' },
})

const apiResponse = (body: unknown, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
})

const input: ExpenseInput = {
    date: '2026-10-12',
    description: 'Compra de teste',
    amountCents: 12550,
    category: 'category-mercado',
    payment: 'credito',
    recurring: true,
}

describe('API run service', () => {
    it('loads assignable leaves, posts an expense, then uses backend dashboard totals', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(apiResponse(envelope({
                categories: [
                    { id: 'category-alimentacao', label: 'Alimentação', parent_category_id: null, is_active: true },
                    { id: 'category-mercado', label: 'Mercado', parent_category_id: 'category-alimentacao', is_active: true },
                    { id: 'category-archived', label: 'Antiga', parent_category_id: 'category-alimentacao', is_active: false },
                ],
            })))
            .mockResolvedValueOnce(apiResponse(envelope({
                expense: {
                    id: 'expense-1',
                    date: input.date,
                    description: input.description,
                    amount_cents: input.amountCents,
                    payment_method: input.payment,
                    recurring: input.recurring,
                    category_id: input.category,
                    created_at: '2026-10-12T10:00:00Z',
                },
            })))
            .mockResolvedValueOnce(apiResponse(envelope({
                dashboard: {
                    month: '2026-10',
                    total_cents: 20250,
                    expense_count: 2,
                    recurring_cents: 15000,
                    category_breakdown: [
                        { category_id: 'category-mercado', label: 'Mercado', amount_cents: 12550 },
                        { category_id: 'category-restaurantes', label: 'Restaurantes', amount_cents: 7700 },
                    ],
                    payment_breakdown: [
                        { payment_method: 'credito', amount_cents: 20250 },
                    ],
                },
            })))
            .mockResolvedValueOnce(apiResponse(envelope({
                insight_run: {
                    cards: [{ title: 'Resumo do mês', text: 'As despesas somaram R$ 202,50.', source_refs: ['source-1'] }],
                },
                sources: {
                    'source-1': [{
                        expense_id: 'expense-1',
                        category_label: 'Mercado',
                        date: input.date,
                        amount_cents: input.amountCents,
                    }],
                },
            })))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')

        await expect(service.getCategories?.()).resolves.toEqual([
            { id: 'category-mercado', label: 'Mercado' },
        ])
        const started = await service.startRun(input)
        const status = await service.getRunStatus(started.runId)

        expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://api.test/expenses', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({
                date: input.date,
                description: input.description,
                amount_cents: input.amountCents,
                payment_method: input.payment,
                category_id: input.category,
                recurring: input.recurring,
            }),
        }))
        expect(fetchMock).toHaveBeenNthCalledWith(3, 'http://api.test/dashboard/monthly?month=2026-10', expect.any(Object))
        expect(fetchMock).toHaveBeenNthCalledWith(4, 'http://api.test/insights/monthly', expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({ month: '2026-10' }),
        }))
        expect(status).toMatchObject({
            status: 'done',
            result: {
                runId: 'expense-1',
                totalCents: 20250,
                count: 2,
                recurringCents: 15000,
                categories: [
                    { name: 'category-mercado', label: 'Mercado', cents: 12550 },
                    { name: 'category-restaurantes', label: 'Restaurantes', cents: 7700 },
                ],
                insight: {
                    title: 'Resumo do mês',
                    text: 'As despesas somaram R$ 202,50.',
                    sources: [{
                        expenseId: 'expense-1',
                        categoryLabel: 'Mercado',
                        date: input.date,
                        amountCents: input.amountCents,
                    }],
                },
            },
        })
    })

    it('surfaces the backend validation message and does not fabricate a completed result', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(apiResponse(envelope({
                categories: [
                    {
                        id: 'category-mercado',
                        label: 'Mercado',
                        parent_category_id: null,
                        is_active: true,
                    },
                ]
            })))
            .mockResolvedValueOnce(apiResponse(envelope(null, [{
                code: 'ParentCategoryNotAssignable',
                message: 'Selecione uma categoria final, não um grupo.',
            }]), 422))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')
        await service.getCategories?.()

        await expect(service.startRun(input)).rejects.toThrow('Selecione uma categoria final')
        await expect(service.getRunStatus('missing')).rejects.toThrow('Execução não encontrada')
    })

    it('retries the dashboard read without duplicating a successfully created expense', async () => {
        const expense = {
            id: 'expense-retry',
            date: input.date,
            description: input.description,
            amount_cents: input.amountCents,
            payment_method: input.payment,
            recurring: input.recurring,
            category_id: input.category,
            created_at: '2026-10-12T10:00:00Z',
        }
        const dashboard = {
            month: '2026-10',
            total_cents: 12550,
            expense_count: 1,
            recurring_cents: 12550,
            category_breakdown: [{ category_id: input.category, label: 'Mercado', amount_cents: 12550 }],
            payment_breakdown: [{ payment_method: input.payment, amount_cents: 12550 }],
        }
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(apiResponse(envelope({ expense })))
            .mockResolvedValueOnce(apiResponse(envelope(null, [{ code: 'temporary', message: 'Dashboard indisponível.' }]), 503))
            .mockResolvedValueOnce(apiResponse(envelope({ dashboard })))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')
        const requestId = 'client-request-retry'

        await expect(service.startRun(input, requestId)).rejects.toThrow('Dashboard indisponível')
        const started = await service.startRun(input, requestId)
        const result = await service.getRunStatus(started.runId)

        expect(fetchMock.mock.calls.filter(([url]) => url === 'http://api.test/expenses')).toHaveLength(1)
        expect(result.status).toBe('done')
    })
})
