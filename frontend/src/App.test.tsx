import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { createRunService } from './services/runs'
import type { RunService } from './workflow'

afterEach(() => vi.useRealTimers())

function fill(description = 'Mercado demo', amount = '123,45') {
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-10-09' } })
    fireEvent.change(screen.getByLabelText('Descrição'), { target: { value: description } })
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: amount } })
}

describe('form/run/results/history integration (AC-P0.3, P0.7 prototype)', () => {
    it('shows a retryable history load error instead of claiming there are no saved expenses', async () => {
        const stub = createRunService(0)
        const getHistory = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue([])
        const service = { ...stub, getHistory, startRun: vi.fn(stub.startRun) }
        render(<App service={service} />)
        expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar as despesas salvas.')
        expect(screen.getByText('Histórico indisponível.')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Tentar carregar novamente' }))
        await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
        expect(getHistory).toHaveBeenCalledTimes(2)
        expect(service.startRun).not.toHaveBeenCalled()
    })

    it('reloads saved backend expenses on mount and remount without creating expenses', async () => {
        const stub = createRunService(0)
        const started = await stub.startRun({ date: '2026-10-09', description: 'Fixture', amountCents: 12345, category: 'category-mercado', payment: 'debito', recurring: false })
        const stored = await stub.getRunStatus(started.runId)
        if (stored.status !== 'done') throw new Error('Expected stored expense')
        const result = { ...stored.result, input: { ...stored.result.input, description: 'Despesa persistida' } }
        const service: RunService = { ...stub, getHistory: vi.fn(async () => [result]), startRun: vi.fn(stub.startRun) }
        const first = render(<App service={service} />)
        expect(await screen.findByRole('button', { name: 'Mostrar detalhes: Despesa persistida' })).toBeInTheDocument()
        expect(screen.getByRole('region', { name: 'Resultados' })).toHaveTextContent('Despesa persistida')
        first.unmount()
        render(<App service={service} />)
        expect(await screen.findByRole('button', { name: 'Mostrar detalhes: Despesa persistida' })).toBeInTheDocument()
        expect(service.getHistory).toHaveBeenCalledTimes(2)
        expect(service.startRun).not.toHaveBeenCalled()
    })

    it('submits automatic categorization and shows the category returned by the backend', async () => {
        const stub = createRunService(0)
        const service: RunService = {
            ...stub,
            startRun: vi.fn(stub.startRun),
            getCategories: async () => [
                { id: 'category-mercado', label: 'Mercado' },
                { id: 'category-transporte', label: 'Transporte' },
            ],
            getRunStatus: async runId => {
                const status = await stub.getRunStatus(runId)
                return status.status === 'done'
                    ? { ...status, result: { ...status.result, input: { ...status.result.input, category: 'category-transporte' } } }
                    : status
            },
        }
        render(<App service={service} />)
        await screen.findByRole('option', { name: 'Transporte' })
        fill('Transporte demo')
        fireEvent.change(screen.getByLabelText('Categoria'), { target: { value: '' } })
        expect(screen.getByRole('option', { name: 'Automatica' })).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Execução: concluída'))
        expect(service.startRun).toHaveBeenCalledWith(expect.objectContaining({ category: '' }), expect.any(String))
        expect(screen.getByRole('region', { name: 'Resultados' }).querySelector('.record')).toHaveTextContent('Transporte')
        expect(screen.getByLabelText('Categoria')).toHaveValue('')
    })

    it('shows a top banner with state colors and real client update timestamps', async () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-10-09T15:00:00Z'))
        render(<App service={createRunService(1200)} />)
        const banner = screen.getByRole('status')
        const timestamp = () => banner.querySelector('time')!.getAttribute('datetime')
        expect(document.querySelector('main')?.firstElementChild).toBe(banner)
        expect(banner).toHaveTextContent('Execução: ociosa')
        expect(banner.querySelector('.crew-state')).toHaveStyle({ color: '#606870' })
        expect(timestamp()).toBe('2026-10-09T15:00:00.000Z')
        vi.advanceTimersByTime(1000)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        expect(banner).toHaveTextContent('Execução: em andamento')
        expect(banner.querySelector('.crew-state')).toHaveStyle({ color: '#1755a6' })
        expect(screen.getByRole('button', { name: 'Execução: em andamento' })).toBeDisabled()
        expect(screen.getByRole('heading', { name: 'Execução: em andamento' })).toBeInTheDocument()
        expect(timestamp()).toBe('2026-10-09T15:00:01.000Z')
        await act(async () => { await vi.advanceTimersByTimeAsync(400) })
        expect(banner).toHaveTextContent('Execução: em andamento')
        expect(timestamp()).toBe('2026-10-09T15:00:01.400Z')
        await act(async () => { await vi.advanceTimersByTimeAsync(800) })
        expect(banner).toHaveTextContent('Execução: concluída')
        expect(banner.querySelector('.crew-state')).toHaveStyle({ color: '#14614d' })
        expect(timestamp()).toBe('2026-10-09T15:00:02.200Z')
        expect(within(screen.getByRole('region', { name: 'Resultados' })).getByText('Execução: concluída')).toBeInTheDocument()
        vi.advanceTimersByTime(1000)
        fireEvent.click(screen.getByRole('button', { name: 'Redefinir' }))
        expect(banner).toHaveTextContent('Execução: ociosa')
        expect(timestamp()).toBe('2026-10-09T15:00:03.200Z')
        await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
        expect(timestamp()).toBe('2026-10-09T15:00:03.200Z')
    })

    it('shows red errors and refreshes timestamps on failure, retry and reset', async () => {
        vi.useFakeTimers()
        vi.setSystemTime(new Date('2026-10-09T15:00:00Z'))
        const stub = createRunService(0)
        const service = { ...stub, startRun: vi.fn(stub.startRun).mockRejectedValueOnce(new Error('Falha simulada.')) }
        render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        await act(async () => { await vi.advanceTimersByTimeAsync(0) })
        const banner = screen.getByRole('status')
        expect(banner).toHaveAttribute('data-state', 'error')
        expect(banner).toHaveTextContent('Execução: erro')
        expect(banner.querySelector('.crew-state')).toHaveStyle({ color: '#b42318' })
        expect(screen.getByRole('alert')).toHaveTextContent('Execução: erro: Falha simulada.')
        vi.advanceTimersByTime(1000)
        fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
        expect(banner).toHaveTextContent('Execução: em andamento')
        await act(async () => { await vi.advanceTimersByTimeAsync(0) })
        expect(banner).toHaveTextContent('Execução: concluída')
        expect(banner.querySelector('time')).toHaveAttribute('datetime', '2026-10-09T15:00:01.000Z')
        fill('Invalid demo', '0')
        vi.advanceTimersByTime(1000)
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        expect(banner).toHaveTextContent('Execução: erro')
        expect(banner.querySelector('time')).toHaveAttribute('datetime', '2026-10-09T15:00:02.000Z')
        vi.advanceTimersByTime(1000)
        fireEvent.click(screen.getByRole('button', { name: 'Redefinir' }))
        expect(banner).toHaveTextContent('Execução: ociosa')
        expect(banner.querySelector('.crew-state')).toHaveStyle({ color: '#606870' })
        expect(banner.querySelector('time')).toHaveAttribute('datetime', '2026-10-09T15:00:03.000Z')
    })

    it('runs once, disables submission, completes, and expands history details', async () => {
        vi.useFakeTimers()
        const stub = createRunService(1200)
        const service = { ...stub, startRun: vi.fn(stub.startRun) }
        render(<App service={service} />)
        fill()
        const submit = screen.getByRole('button', { name: 'Executar' })
        fireEvent.click(submit)
        fireEvent.click(submit)
        expect(submit).toBeDisabled()
        expect(screen.getByRole('button', { name: 'Redefinir' })).toBeDisabled()
        expect(screen.getByRole('status')).toHaveTextContent('Execução: em andamento')
        expect(screen.getByLabelText('Descrição')).toBeDisabled()
        expect(service.startRun).toHaveBeenCalledTimes(1)
        await act(async () => { await vi.advanceTimersByTimeAsync(1600) })
        expect(screen.getByRole('status')).toHaveTextContent('Execução: concluída')
        expect(screen.getByRole('button', { name: 'Mostrar detalhes: Mercado demo' })).toHaveAttribute('aria-expanded', 'false')
        expect(screen.getByLabelText('Descrição')).toHaveValue('')
        expect(screen.getByLabelText('Categoria')).toHaveValue('category-mercado')
        expect(screen.getByRole('heading', { name: 'Resultados' })).toHaveFocus()
        fill('Aluguel demo', '1000,00')
        fireEvent.change(screen.getByLabelText('Categoria'), { target: { value: 'category-moradia' } })
        fireEvent.click(screen.getByLabelText('Despesa recorrente'))
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        await act(async () => { await vi.advanceTimersByTimeAsync(1600) })
        const results = screen.getByRole('region', { name: 'Resultados' })
        expect(within(results).getByText('Total registrado').parentElement).toHaveTextContent('R$ 123,45')
        expect(within(results).getByText('Despesas').parentElement).toHaveTextContent('01')
        const historyRow = screen.getByRole('button', { name: 'Mostrar detalhes: Mercado demo' })
        fireEvent.click(historyRow)
        expect(screen.getByRole('button', { name: 'Ocultar detalhes: Mercado demo' })).toHaveAttribute('aria-expanded', 'true')
        const details = screen.getByRole('group', { name: 'Detalhes de Mercado demo' })
        expect(within(details).getByRole('heading', { name: 'Detalhes da despesa' })).toBeInTheDocument()
        expect(within(details).getByText('Mercado')).toBeInTheDocument()
        expect(within(details).getByText('Débito')).toBeInTheDocument()
        expect(within(details).getByText('Não')).toBeInTheDocument()
        expect(within(results).getByText('Aluguel demo')).toBeInTheDocument()
        expect(screen.getByLabelText('Categoria')).toHaveValue('category-moradia')
        fireEvent.click(screen.getByRole('button', { name: 'Ocultar detalhes: Mercado demo' }))
        expect(screen.getByRole('button', { name: 'Mostrar detalhes: Mercado demo' })).toHaveAttribute('aria-expanded', 'false')
    })

    it('rejects invalid BRL without starting a run', () => {
        const service = { ...createRunService(), startRun: vi.fn() }
        render(<App service={service} />)
        fill('Demo', '0')
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        expect(screen.getByRole('alert')).toHaveTextContent('O valor deve estar')
        expect(service.startRun).not.toHaveBeenCalled()
    })

    it('preserves fields on a start failure and supports retry', async () => {
        const stub = createRunService(0)
        const service = { ...stub, startRun: vi.fn(stub.startRun).mockRejectedValueOnce(new Error('Falha simulada. Tente novamente.')) }
        render(<App service={service} />)
        fill()
        fireEvent.change(screen.getByLabelText('Categoria'), { target: { value: 'category-moradia' } })
        fireEvent.change(screen.getByLabelText('Forma de pagamento'), { target: { value: 'credito' } })
        fireEvent.click(screen.getByLabelText('Despesa recorrente'))
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('Falha simulada')
        expect(screen.getByLabelText('Valor')).toHaveValue('123,45')
        const originalInput = service.startRun.mock.calls[0][0]
        fill('Editado depois da falha', '999,99')
        fireEvent.change(screen.getByLabelText('Categoria'), { target: { value: 'Outros' } })
        fireEvent.change(screen.getByLabelText('Forma de pagamento'), { target: { value: 'dinheiro' } })
        fireEvent.click(screen.getByLabelText('Despesa recorrente'))
        fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }))
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Execução: concluída'))
        expect(service.startRun.mock.calls[1][0]).toEqual(originalInput)
        expect(screen.getByLabelText('Categoria')).toHaveValue('category-moradia')
        expect(screen.getByLabelText('Forma de pagamento')).toHaveValue('credito')
        expect(screen.getByLabelText('Despesa recorrente')).toBeChecked()
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('offers review navigation when monthly insights are held for pending expenses', async () => {
        const stub = createRunService(0)
        const service = {
            ...stub,
            getRunStatus: async (runId: string) => {
                const status = await stub.getRunStatus(runId)
                return status.status === 'done'
                    ? { status: 'done' as const, result: { ...status.result, pendingReviewCount: 2 } }
                    : status
            },
        }
        render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))

        expect(await screen.findByText('2 despesas precisam de revisão antes dos insights do mês.')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Revisar despesas' })).toBeInTheDocument()
    })

    it('asks the user to verify reviews when the pending status could not be loaded', async () => {
        const stub = createRunService(0)
        const service = {
            ...stub,
            getRunStatus: async (runId: string) => {
                const status = await stub.getRunStatus(runId)
                return status.status === 'done'
                    ? { status: 'done' as const, result: { ...status.result, pendingReviewCount: null } }
                    : status
            },
        }
        render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))

        expect(await screen.findByText('Não foi possível confirmar as pendências. Os insights foram adiados.')).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Conferir despesas' })).toBeInTheDocument()
    })

    it('communicates deterministic fallback when the API reports a provider failure', async () => {
        const stub = createRunService(0)
        const service = {
            ...stub,
            getRunStatus: async (runId: string) => {
                const status = await stub.getRunStatus(runId)
                return status.status === 'done'
                    ? { status: 'done' as const, result: { ...status.result, insightProviderStatus: 'failed' as const, insightProviderErrorCode: 'rate_limit' as const } }
                    : status
            },
        }
        render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))

        expect(await screen.findByText('O GitHub Copilot atingiu um limite de uso ou de créditos.')).toBeInTheDocument()
    })

    it('handles status failure without creating completed history', async () => {
        render(<App service={{ startRun: async () => ({ runId: 'demo' }), getRunStatus: async () => { throw new Error('Status indisponível.') } }} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('Status indisponível')
        expect(screen.queryByRole('button', { name: 'Mostrar detalhes: Mercado demo' })).not.toBeInTheDocument()
    })

    it('resets errors, form defaults and results to idle while retaining history', async () => {
        render(<App service={createRunService(0)} />)
        expect(screen.getByRole('status')).toHaveTextContent('Execução: ociosa')
        fill('Invalid demo', '0')
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        expect(screen.getByRole('alert')).toBeInTheDocument()
        fireEvent.click(screen.getByRole('button', { name: 'Redefinir' }))
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
        fill()
        fireEvent.change(screen.getByLabelText('Categoria'), { target: { value: 'category-moradia' } })
        fireEvent.click(screen.getByLabelText('Despesa recorrente'))
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Execução: concluída'))
        fireEvent.click(screen.getByRole('button', { name: 'Redefinir' }))
        expect(screen.getByRole('status')).toHaveTextContent('Execução: ociosa')
        expect(screen.getByLabelText('Descrição')).toHaveValue('')
        expect(screen.getByLabelText('Valor')).toHaveValue('')
        expect(screen.getByLabelText('Categoria')).toHaveValue('category-mercado')
        expect(screen.getByLabelText('Despesa recorrente')).not.toBeChecked()
        expect(screen.getByLabelText('Descrição')).toHaveFocus()
        expect(screen.getByRole('heading', { name: 'Nenhum resultado por aqui' })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: 'Mostrar detalhes: Mercado demo' })).toHaveAttribute('aria-expanded', 'false')
        expect(screen.queryByRole('button', { name: 'Tentar novamente' })).not.toBeInTheDocument()
        fill('Depois do reset')
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Execução: concluída'))
        expect(screen.getByRole('button', { name: 'Mostrar detalhes: Depois do reset' })).toBeInTheDocument()
    })

    it('stops polling on unmount', async () => {
        vi.useFakeTimers()
        const service: RunService = { startRun: async () => ({ runId: 'demo' }), getRunStatus: vi.fn(async () => ({ status: 'running' as const })) }
        const { unmount } = render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Executar' }))
        await act(async () => { await vi.advanceTimersByTimeAsync(100) })
        expect(service.getRunStatus).toHaveBeenCalledTimes(1)
        unmount()
        await act(async () => { await vi.advanceTimersByTimeAsync(15_000) })
        expect(service.getRunStatus).toHaveBeenCalledTimes(1)
        expect(vi.getTimerCount()).toBe(0)
    })

    it('provides semantic headings and keyboard access to Run and Reset', async () => {
        const user = userEvent.setup()
        render(<App service={createRunService(0)} />)
        expect(screen.getByRole('heading', { level: 1, name: 'Despesas da casa' })).toBeInTheDocument()
        expect(screen.getByRole('heading', { level: 2, name: 'Resultados' })).toBeInTheDocument()
        await user.tab()
        expect(screen.getByRole('link', { name: 'Ir para o conteúdo' })).toHaveFocus()
        for (const label of ['Data', 'Descrição', 'Valor', 'Categoria', 'Forma de pagamento', 'Despesa recorrente']) {
            await user.tab()
            expect(screen.getByLabelText(label)).toHaveFocus()
        }
        await user.keyboard('[Space]')
        expect(screen.getByLabelText('Despesa recorrente')).toBeChecked()
        await user.tab()
        expect(screen.getByRole('button', { name: 'Executar' })).toHaveFocus()
        await user.tab()
        expect(screen.getByRole('button', { name: 'Redefinir' })).toHaveFocus()
        await user.keyboard('[Enter]')
        expect(screen.getByLabelText('Despesa recorrente')).not.toBeChecked()
        expect(screen.getByLabelText('Descrição')).toHaveFocus()
        expect(screen.getAllByRole('button')).toHaveLength(2)
    })
})