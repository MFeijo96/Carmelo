import { afterEach, describe, expect, it, vi } from 'vitest'
import { householdService } from './household'

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
    blob: async () => new Blob(['exported']),
})

describe('household API service', () => {
    it('uploads raw CSV and maps the import report envelope', async () => {
        const csv = 'data,descricao,valor,forma_pagamento\n12/10/2026,Compra,12,50,credito'
        const file = { name: 'casa.csv', text: async () => csv } as File
        const fetchMock = vi.fn().mockResolvedValue(apiResponse(envelope({
            import_run: { id: 'import-1', total_rows: 1, imported_rows: 1, rejected_rows: 0, row_errors: [], status: 'completed' },
        })))
        vi.stubGlobal('fetch', fetchMock)

        await expect(householdService.importCsv(file)).resolves.toMatchObject({ imported_rows: 1 })
        expect(fetchMock).toHaveBeenCalledWith(
            'http://127.0.0.1:8000/imports/csv?source_name=casa.csv',
            expect.objectContaining({
                method: 'POST',
                headers: { Accept: 'application/json', 'Content-Type': 'text/csv' },
                body: csv,
            }),
        )
    })

    it('maps every expense-review filter and pagination offset to the API query', async () => {
        const fetchMock = vi.fn().mockResolvedValue(apiResponse(envelope({ expenses: [], total_count: 0 })))
        vi.stubGlobal('fetch', fetchMock)

        await expect(householdService.listExpenses({
            month: '2026-10',
            categoryId: 'category-mercado',
            confidenceMin: 0.7,
            paymentMethod: 'credito',
            source: 'csv',
            reviewRequired: true,
            offset: 100,
        })).resolves.toEqual({ expenses: [], totalCount: 0 })
        expect(fetchMock).toHaveBeenCalledWith(
            'http://127.0.0.1:8000/expenses?month=2026-10&limit=100&offset=100&category_id=category-mercado&confidence_min=0.7&payment_method=credito&source=csv&review_required=true',
            expect.any(Object),
        )
    })

    it('surfaces structured backend errors for destructive operations', async () => {
        const fetchMock = vi.fn().mockResolvedValue(apiResponse(envelope(null, [{ code: 'missing', message: 'Casa não encontrada.' }]), 404))
        vi.stubGlobal('fetch', fetchMock)

        await expect(householdService.deleteDemoData('missing')).rejects.toThrow('Casa não encontrada.')
        expect(fetchMock).toHaveBeenCalledWith(
            'http://127.0.0.1:8000/households/missing/demo-data',
            expect.objectContaining({ method: 'DELETE' }),
        )
    })

    it('returns raw CSV export as a downloadable blob', async () => {
        const exportedBlob = { type: 'text/csv' } as Blob
        const fetchMock = vi.fn().mockResolvedValue({ ...apiResponse(null), blob: async () => exportedBlob })
        vi.stubGlobal('fetch', fetchMock)

        const blob = await householdService.exportCsv()

        expect(blob).toBe(exportedBlob)
        expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:8000/exports/expenses.csv', expect.any(Object))
    })
})
