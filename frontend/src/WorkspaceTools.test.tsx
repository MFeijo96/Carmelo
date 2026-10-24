import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import WorkspaceTools from './WorkspaceTools'
import type { HouseholdCategory, HouseholdExpense, HouseholdService } from './services/household'

const categories: HouseholdCategory[] = [
    { id: 'food', label: 'Alimentação', parent_category_id: null, is_active: true, is_standard: true },
    { id: 'market', label: 'Mercado', parent_category_id: 'food', is_active: true, is_standard: true },
    { id: 'other', label: 'Outros', parent_category_id: null, is_active: true, is_standard: true },
    { id: 'custom', label: 'Refeições', parent_category_id: 'food', is_active: true, is_standard: false },
]

const expense: HouseholdExpense = {
    id: 'expense-1', date: '2026-10-09', description: 'Compra da casa', amount_cents: 1250,
    payment_method: 'credito', recurring: false, category_id: 'market', source: 'manual',
    confidence: 0.4, review_required: true, user_override: false,
}

function serviceMock(): HouseholdService {
    let pendingReview = true
    return {
        listCategories: vi.fn(async () => categories),
        listExpenses: vi.fn(async filters => filters.reviewRequired
            ? { expenses: pendingReview ? [expense] : [], totalCount: pendingReview ? 1 : 0 }
            : { expenses: [expense], totalCount: 1 }),
        importCsv: vi.fn(async () => ({ id: 'import-1', total_rows: 2, imported_rows: 1, rejected_rows: 1, row_errors: [{ row: 3, field: 'valor', code: 'invalid', message: 'Informe um valor BRL.', value: 'abc' }], status: 'completed' })),
        correctCategory: vi.fn(async (_id, categoryId) => { pendingReview = false; return { ...expense, category_id: categoryId, review_required: false, user_override: true } }),
        generateInsights: vi.fn(async () => ({
            title: 'Resumo do mês', text: 'As despesas foram registradas.', sources: [],
            providerStatus: 'failed' as const, providerErrorCode: 'rate_limit' as const,
        })),
        createCategory: vi.fn(async label => ({ id: 'created', label, parent_category_id: 'food', is_active: true, is_standard: false })),
        renameCategory: vi.fn(async (id, label) => ({ ...categories[3], id, label })),
        mergeCategories: vi.fn(async () => categories[2]),
        exportCsv: vi.fn(async () => new Blob(['data'])),
        exportArchive: vi.fn(async () => new Blob(['{}'], { type: 'application/json' })),
        getDemoHouseholdId: vi.fn(async () => 'demo-household'),
        deleteDemoData: vi.fn(async () => undefined),
        evaluate: vi.fn(async () => ({ total_count: 30, correct_count: 24, accuracy: 0.8, passed: true, confusion_details: [{ expected_category_id: 'market', predicted_category_id: 'other', count: 2 }] })),
    }
}

describe('household operations', () => {
    it('opens the pending-review tab when requested from the result screen', async () => {
        const service = serviceMock()
        const { rerender } = render(<WorkspaceTools service={service} reviewRequest={0} />)
        const descriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView')
        const scrollIntoView = vi.fn()
        Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView })

        try {
            rerender(<WorkspaceTools service={service} reviewRequest={1} />)

            expect(screen.getByRole('tab', { name: 'Despesas' })).toHaveAttribute('aria-selected', 'true')
            expect(screen.getByLabelText('Pendentes de revisão')).toBeChecked()
            await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' }))
            expect(screen.getByRole('heading', { name: 'Revisar despesas' })).toBeInTheDocument()
        } finally {
            if (descriptor) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', descriptor)
            else delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView
        }
    })

    it('refreshes expenses when a new expense is registered while the tab is open', async () => {
        const service = serviceMock()
        const { rerender } = render(<WorkspaceTools service={service} expenseRefreshRequest={0} />)
        await userEvent.click(screen.getByRole('tab', { name: 'Despesas' }))
        await screen.findByText('Compra da casa')

        const newExpense = { ...expense, id: 'expense-2', description: 'Compra em Outros', category_id: 'other' }
        vi.mocked(service.listExpenses).mockResolvedValue({
            expenses: [newExpense],
            totalCount: 1,
        })
        const callsBeforeRefresh = vi.mocked(service.listExpenses).mock.calls.length
        rerender(<WorkspaceTools service={service} expenseRefreshRequest={1} />)

        expect(await screen.findByText('Compra em Outros')).toBeInTheDocument()
        expect(screen.queryByText('Compra da casa')).not.toBeInTheDocument()
        expect(service.listExpenses).toHaveBeenCalledTimes(callsBeforeRefresh + 3)
    })

    it('shows CSV row errors and accepted/rejected counts', async () => {
        const user = userEvent.setup()
        const service = serviceMock()
        render(<WorkspaceTools service={service} />)
        await screen.findByRole('heading', { name: 'Importar despesas CSV' })
        await user.upload(screen.getByLabelText('Arquivo CSV'), new File(['data,descricao'], 'casa.csv', { type: 'text/csv' }))
        await user.click(screen.getByRole('button', { name: 'Importar arquivo' }))

        expect(await screen.findByText('1 importadas')).toBeInTheDocument()
        expect(screen.getByText(/Linha 3, valor: Informe um valor BRL/)).toBeInTheDocument()
        expect(service.importCsv).toHaveBeenCalledOnce()
    })

    it('lists expenses and records a user category correction', async () => {
        const user = userEvent.setup()
        const service = serviceMock()
        render(<WorkspaceTools service={service} />)
        await user.click(screen.getByRole('tab', { name: 'Despesas' }))
        await screen.findByText('Compra da casa')
        await user.selectOptions(screen.getByLabelText('Categoria'), 'other')
        await user.selectOptions(screen.getByLabelText('Confiança mínima'), '0.7')
        await user.selectOptions(screen.getByLabelText('Pagamento'), 'credito')
        await user.selectOptions(screen.getByLabelText('Origem'), 'csv')
        await user.click(screen.getByLabelText('Pendentes de revisão'))
        await waitFor(() => expect(service.listExpenses).toHaveBeenCalledWith({
            month: expect.any(String),
            categoryId: 'other',
            confidenceMin: 0.7,
            paymentMethod: 'credito',
            source: 'csv',
            reviewRequired: true,
            offset: 0,
        }))
        fireEvent.change(screen.getByLabelText('Categoria de Compra da casa'), { target: { value: 'other' } })

        await waitFor(() => expect(service.correctCategory).toHaveBeenCalledWith('expense-1', 'other'))
        expect(service.listExpenses).toHaveBeenCalledWith(expect.objectContaining({ month: expect.any(String) }))
        expect(await screen.findByRole('button', { name: 'Gerar insights do mês' })).toBeEnabled()
        expect(screen.queryByText(/Revise 1 despesa pendente/)).not.toBeInTheDocument()
        expect(service.generateInsights).not.toHaveBeenCalled()
        await user.click(screen.getByRole('button', { name: 'Gerar insights do mês' }))
        expect(await screen.findByText('As despesas foram registradas.')).toBeInTheDocument()
        expect(screen.getByText('O GitHub Copilot atingiu um limite de uso ou de créditos.')).toBeInTheDocument()
        expect(service.generateInsights).toHaveBeenCalledOnce()
    })

    it('creates a child category under a top-level category', async () => {
        const user = userEvent.setup()
        const service = serviceMock()
        render(<WorkspaceTools service={service} />)
        await user.click(screen.getByRole('tab', { name: 'Categorias' }))
        await user.type(screen.getByLabelText('Nova categoria'), 'Feira')
        await user.click(screen.getByRole('button', { name: 'Criar folha' }))

        await waitFor(() => expect(service.createCategory).toHaveBeenCalledWith('Feira', 'food'))
        expect(await screen.findByText('Categoria criada.')).toBeInTheDocument()
    })

    it('renames and merges household categories through their API actions', async () => {
        const user = userEvent.setup()
        const service = serviceMock()
        render(<WorkspaceTools service={service} />)
        await user.click(screen.getByRole('tab', { name: 'Categorias' }))
        await user.type(screen.getByLabelText('Novo nome'), 'Refeições e lanches')
        await user.click(screen.getByRole('button', { name: 'Renomear' }))
        await waitFor(() => expect(service.renameCategory).toHaveBeenCalledWith('custom', 'Refeições e lanches'))
        await user.click(screen.getByRole('button', { name: 'Mesclar' }))
        await waitFor(() => expect(service.mergeCategories).toHaveBeenCalledWith('custom', 'market'))
    })

    it('shows the deterministic evaluation numerator and denominator', async () => {
        const user = userEvent.setup()
        const service = serviceMock()
        render(<WorkspaceTools service={service} />)
        await user.click(screen.getByRole('tab', { name: 'Avaliação' }))
        await user.click(screen.getByRole('button', { name: 'Executar avaliação' }))

        expect(await screen.findByText('24 acertos de 30 registros')).toBeInTheDocument()
        expect(screen.getByText('Mercado → Outros: 2')).toBeInTheDocument()
        expect(service.evaluate).toHaveBeenCalledOnce()
    })

    it('requires confirmation before deleting demo data', async () => {
        const user = userEvent.setup()
        const service = serviceMock()
        const onDataDeleted = vi.fn()
        vi.spyOn(window, 'confirm').mockReturnValue(true)
        render(<WorkspaceTools service={service} onDataDeleted={onDataDeleted} />)
        await user.click(screen.getByRole('tab', { name: 'Dados' }))
        await user.click(screen.getByRole('button', { name: 'Apagar dados da demonstração' }))

        await waitFor(() => expect(service.deleteDemoData).toHaveBeenCalledWith('demo-household'))
        expect(onDataDeleted).toHaveBeenCalledOnce()
        expect(await screen.findByText('Dados da casa demonstrativa apagados.')).toBeInTheDocument()
        vi.mocked(window.confirm).mockRestore()
    })

    it('requests both export formats', async () => {
        const user = userEvent.setup()
        const service = serviceMock()
        const createUrl = vi.fn(() => 'blob:download')
        const revokeUrl = vi.fn()
        const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
        Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createUrl })
        Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeUrl })
        render(<WorkspaceTools service={service} />)
        await user.click(screen.getByRole('tab', { name: 'Dados' }))
        await user.click(screen.getByRole('button', { name: 'Baixar despesas CSV' }))
        await waitFor(() => expect(service.exportCsv).toHaveBeenCalledOnce())
        await user.click(screen.getByRole('button', { name: 'Baixar arquivo JSON' }))
        await waitFor(() => expect(service.exportArchive).toHaveBeenCalledOnce())
        expect(anchorClick).toHaveBeenCalledTimes(2)
        expect(createUrl).toHaveBeenCalledTimes(2)
        anchorClick.mockRestore()
    })
})