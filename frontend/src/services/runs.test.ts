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
    it('restores every saved page and authoritative monthly totals using read-only requests', async () => {
        const expense = {
            id: 'saved', date: input.date, description: input.description,
            amount_cents: input.amountCents, payment_method: input.payment, recurring: input.recurring,
            category_id: input.category, created_at: '2026-10-12T10:00:00Z',
        }
        const firstPage = Array.from({ length: 100 }, (_, index) => ({ ...expense, id: `saved-${index}`, review_required: index === 0 }))
        const last = { ...expense, id: 'saved-latest', date: '2026-11-01', created_at: '2026-11-01T10:00:00Z', review_required: true }
        const dashboard = { month: '2026-10', total_cents: 4321, expense_count: 100, recurring_cents: 500, category_breakdown: [], payment_breakdown: [] }
        const fetchMock = vi.fn(async (url: string) => {
            if (url.includes('/expenses?offset=0')) return apiResponse(envelope({ expenses: firstPage, total_count: 101 }))
            if (url.includes('/expenses?offset=100')) return apiResponse(envelope({ expenses: [last], total_count: 101 }))
            return apiResponse(envelope({ dashboard: { ...dashboard, month: new URL(url).searchParams.get('month') } }))
        })
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')
        const history = await service.getHistory!()

        expect(history).toHaveLength(101)
        expect(history[0]).toMatchObject({ runId: last.id, month: '2026-11', totalCents: 4321, pendingReviewCount: 1 })
        expect(history.find(result => result.runId === 'saved-0')).toMatchObject({ month: '2026-10', totalCents: 4321, pendingReviewCount: 1 })
        expect(fetchMock).toHaveBeenCalledTimes(4)
        expect(fetchMock).toHaveBeenCalledWith('http://api.test/expenses?offset=100&limit=100', expect.anything())
        expect(fetchMock.mock.calls.every(([url]) => !url.includes('/insights/'))).toBe(true)
        await expect(service.getRunStatus(last.id)).resolves.toMatchObject({ status: 'done', result: history[0] })
    })

    it('returns an empty persisted history without dashboard or provider requests', async () => {
        const fetchMock = vi.fn().mockResolvedValue(apiResponse(envelope({ expenses: [], total_count: 0 })))
        vi.stubGlobal('fetch', fetchMock)
        await expect(createApiRunService('http://api.test').getHistory!()).resolves.toEqual([])
        expect(fetchMock).toHaveBeenCalledTimes(1)
    })

    it.each(['category-mercado', ''])('saves manual or automatic category %s without generating insights', async category => {
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
            .mockResolvedValueOnce(apiResponse(envelope({ total_count: 0 })))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')

        await expect(service.getCategories?.()).resolves.toEqual([
            { id: 'category-mercado', label: 'Mercado' },
        ])
        const started = await service.startRun({ ...input, category })
        const status = await service.getRunStatus(started.runId)

        expect(fetchMock).toHaveBeenNthCalledWith(2, 'http://api.test/expenses', expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({ 'Idempotency-Key': expect.any(String) }),
            body: JSON.stringify({
                date: input.date,
                description: input.description,
                amount_cents: input.amountCents,
                payment_method: input.payment,
                category_id: category || null,
                recurring: input.recurring,
            }),
        }))
        expect(fetchMock).toHaveBeenNthCalledWith(3, 'http://api.test/dashboard/monthly?month=2026-10', expect.any(Object))
        expect(fetchMock).toHaveBeenNthCalledWith(4, 'http://api.test/expenses?month=2026-10&review_required=true&limit=1', expect.any(Object))
        expect(fetchMock).toHaveBeenCalledTimes(4)
        expect(fetchMock).not.toHaveBeenCalledWith('http://api.test/insights/monthly', expect.anything())
        expect(status).toMatchObject({
            status: 'done',
            result: {
                runId: 'expense-1',
                input: { category: 'category-mercado' },
                totalCents: 20250,
                count: 2,
                recurringCents: 15000,
                pendingReviewCount: 0,
                categories: [
                    { name: 'category-mercado', label: 'Mercado', cents: 12550 },
                    { name: 'category-restaurantes', label: 'Restaurantes', cents: 7700 },
                ],
            },
        })
    })

    it('does not request monthly insights while the month has pending review items', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(apiResponse(envelope({
                expense: {
                    id: 'expense-review', date: input.date, description: input.description,
                    amount_cents: input.amountCents, payment_method: input.payment,
                    recurring: input.recurring, category_id: input.category,
                    created_at: '2026-10-12T10:00:00Z',
                }
            })))
            .mockResolvedValueOnce(apiResponse(envelope({
                dashboard: {
                    month: '2026-10', total_cents: input.amountCents, expense_count: 1,
                    recurring_cents: input.amountCents, category_breakdown: [], payment_breakdown: [],
                }
            })))
            .mockResolvedValueOnce(apiResponse(envelope({ total_count: 2 })))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')

        const started = await service.startRun(input)
        const result = await service.getRunStatus(started.runId)

        expect(fetchMock).not.toHaveBeenCalledWith('http://api.test/insights/monthly', expect.anything())
        expect(result).toMatchObject({
            status: 'done',
            result: { pendingReviewCount: 2 },
        })
    })

    it('completes the saved expense but withholds insights when review status is unavailable', async () => {
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(apiResponse(envelope({
                expense: {
                    id: 'expense-review-status', date: input.date, description: input.description,
                    amount_cents: input.amountCents, payment_method: input.payment,
                    recurring: input.recurring, category_id: input.category,
                    created_at: '2026-10-12T10:00:00Z',
                }
            })))
            .mockResolvedValueOnce(apiResponse(envelope({
                dashboard: {
                    month: '2026-10', total_cents: input.amountCents, expense_count: 1,
                    recurring_cents: input.amountCents, category_breakdown: [], payment_breakdown: [],
                }
            })))
            .mockResolvedValueOnce(apiResponse(envelope(null, [{ code: 'unavailable', message: 'Review status unavailable.' }]), 503))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')

        const started = await service.startRun(input)
        const result = await service.getRunStatus(started.runId)

        expect(result).toMatchObject({ status: 'done', result: { pendingReviewCount: null } })
        expect(fetchMock).not.toHaveBeenCalledWith('http://api.test/insights/monthly', expect.anything())
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
            .mockResolvedValueOnce(apiResponse(envelope({ total_count: 1 })))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')
        const requestId = 'fc8f7de3-1a6e-4d58-90b4-8f139c8201cd'

        await expect(service.startRun(input, requestId)).rejects.toThrow('Dashboard indisponível')
        const started = await service.startRun(input, requestId)
        const result = await service.getRunStatus(started.runId)

        expect(fetchMock.mock.calls.filter(([url]) => url === 'http://api.test/expenses')).toHaveLength(1)
        expect(result.status).toBe('done')
    })

    it('reuses the same idempotency key when the expense response is lost', async () => {
        const expense = {
            id: 'expense-after-lost-response', date: input.date, description: input.description,
            amount_cents: input.amountCents, payment_method: input.payment,
            recurring: input.recurring, category_id: input.category,
            created_at: '2026-10-12T10:00:00Z',
        }
        const fetchMock = vi.fn()
            .mockRejectedValueOnce(new TypeError('connection dropped after write'))
            .mockResolvedValueOnce(apiResponse(envelope({ expense })))
            .mockResolvedValueOnce(apiResponse(envelope({
                dashboard: {
                    month: '2026-10', total_cents: input.amountCents, expense_count: 1,
                    recurring_cents: input.amountCents, category_breakdown: [], payment_breakdown: [],
                }
            })))
            .mockResolvedValueOnce(apiResponse(envelope({ total_count: 0 })))
        vi.stubGlobal('fetch', fetchMock)
        const service = createApiRunService('http://api.test')
        const requestId = 'ad51c0ab-6811-42aa-968d-214a0f985a72'

        await expect(service.startRun(input, requestId)).rejects.toThrow('Backend indisponível')
        const started = await service.startRun(input, requestId)
        const keys = fetchMock.mock.calls.slice(0, 2).map(([, init]) => init.headers['Idempotency-Key'])

        expect(keys).toEqual([requestId, requestId])
        expect(fetchMock).not.toHaveBeenCalledWith('http://api.test/insights/monthly', expect.anything())
        await expect(service.getRunStatus(started.runId)).resolves.toMatchObject({
            result: { pendingReviewCount: 0 },
        })
    })
})
