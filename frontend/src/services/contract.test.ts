import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { householdService } from './household'
import { createApiRunService } from './runs'

afterEach(() => vi.unstubAllGlobals())

type Spec = { paths: Record<string, Record<string, unknown>> }
const spec = JSON.parse(readFileSync('../backend/openapi.json', 'utf-8')) as Spec

const operations = Object.entries(spec.paths).flatMap(([path, methods]) =>
    Object.keys(methods).map(method => ({
        method: method.toUpperCase(),
        pattern: new RegExp(`^${path.replace(/\{[^}]+\}/g, '[^/]+')}$`),
    })),
)

const documented = (method: string, url: string) =>
    operations.some(operation => operation.method === method && operation.pattern.test(new URL(url).pathname))

const envelope = (data: unknown) => ({ ok: true, status: 200, json: async () => ({ data, errors: [], meta: {} }), blob: async () => ({}) })

const expense = { id: 'expense-1', date: '2026-10-12', description: 'Teste', amount_cents: 100, payment_method: 'debito', recurring: false, category_id: 'category-mercado', created_at: '2026-10-12T10:00:00Z' }
const dashboard = { month: '2026-10', total_cents: 100, expense_count: 1, recurring_cents: 0, category_breakdown: [], payment_breakdown: [] }

function respond(url: string) {
    const parsed = new URL(url)
    const path = parsed.pathname
    if (path === '/expenses' && parsed.searchParams.get('review_required') === 'true') {
        return envelope({ total_count: 0 })
    }
    if (path === '/expenses') return envelope({ expense, expenses: [expense], total_count: 1 })
    if (path === '/dashboard/monthly') return envelope({ dashboard })
    if (path === '/insights/monthly') return envelope({ insight_run: { cards: [] }, sources: {} })
    return envelope({ categories: [] })
}

describe('frontend requests match the committed backend OpenAPI contract', () => {
    it('only calls documented operations', async () => {
        const calls: { method: string; url: string }[] = []
        vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
            calls.push({ method: init?.method ?? 'GET', url })
            return respond(url)
        }))
        const file = { name: 'casa.csv', text: async () => 'data' } as File
        const attempts: Promise<unknown>[] = [
            householdService.listCategories(),
            householdService.listExpenses({ month: '2026-10' }),
            householdService.generateInsights('2026-10'),
            householdService.importCsv(file),
            householdService.correctCategory('expense-1', 'category-mercado'),
            householdService.createCategory('Feira', 'category-alimentacao'),
            householdService.renameCategory('category-custom-1', 'Nova'),
            householdService.mergeCategories('category-custom-1', 'category-mercado'),
            householdService.exportCsv(),
            householdService.exportArchive(),
            householdService.getDemoHouseholdId(),
            householdService.deleteDemoData('demo-household'),
            householdService.evaluate(),
            createApiRunService('http://127.0.0.1:8000').getCategories?.() ?? Promise.resolve(),
            createApiRunService('http://127.0.0.1:8000').getHistory?.() ?? Promise.resolve(),
            createApiRunService('http://127.0.0.1:8000').startRun({
                date: '2026-10-12', description: 'Teste', amountCents: 100,
                category: 'category-mercado', payment: 'debito', recurring: false,
            }),
        ]
        await Promise.allSettled(attempts)

        const paths = new Set(calls.map(call => `${call.method} ${new URL(call.url).pathname}`))
        expect(paths).toContain('GET /dashboard/monthly')
        expect(paths).toContain('POST /insights/monthly')
        const undocumented = calls.filter(call => !documented(call.method, call.url))
        expect(undocumented).toEqual([])
    })
})
