import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
    it('runs once, disables submission, completes, and selects immutable history', async () => {
        vi.useFakeTimers()
        const stub = createRunService(1200)
        const service = { ...stub, startRun: vi.fn(stub.startRun) }
        render(<App service={service} />)
        fill()
        const submit = screen.getByRole('button', { name: 'Registrar e analisar' })
        fireEvent.click(submit)
        fireEvent.click(submit)
        expect(screen.getByRole('button', { name: 'Processando...' })).toBeDisabled()
        expect(screen.getByLabelText('Descrição')).toBeDisabled()
        expect(service.startRun).toHaveBeenCalledTimes(1)
        await act(async () => { await vi.advanceTimersByTimeAsync(1600) })
        expect(screen.getByRole('status')).toHaveTextContent('Execução concluída')
        expect(screen.getByRole('button', { name: 'Ver resultado: Mercado demo' })).toHaveAttribute('aria-pressed', 'true')
        expect(screen.getByLabelText('Descrição')).toHaveValue('')
        expect(screen.getByLabelText('Categoria')).toHaveValue('Alimentacao')
        expect(screen.getByRole('heading', { name: 'Resultados' })).toHaveFocus()
        fill('Aluguel demo', '1000,00')
        fireEvent.change(screen.getByLabelText('Categoria'), { target: { value: 'Moradia' } })
        fireEvent.click(screen.getByLabelText('Despesa recorrente'))
        fireEvent.click(screen.getByRole('button', { name: 'Registrar e analisar' }))
        await act(async () => { await vi.advanceTimersByTimeAsync(1600) })
        const results = screen.getByRole('region', { name: 'Resultados' })
        expect(within(results).getByText('Total registrado').parentElement).toHaveTextContent('R$ 1.123,45')
        expect(within(results).getByText('Despesas').parentElement).toHaveTextContent('02')
        fireEvent.click(screen.getByRole('button', { name: 'Ver resultado: Mercado demo' }))
        expect(within(results).queryByText('R$ 1.123,45')).not.toBeInTheDocument()
        expect(within(results).getByText('01')).toBeInTheDocument()
        expect(screen.getByLabelText('Categoria')).toHaveValue('Moradia')
    })

    it('rejects invalid BRL without starting a run', () => {
        const service = { ...createRunService(), startRun: vi.fn() }
        render(<App service={service} />)
        fill('Demo', '0')
        fireEvent.click(screen.getByRole('button', { name: 'Registrar e analisar' }))
        expect(screen.getByRole('alert')).toHaveTextContent('O valor deve estar')
        expect(service.startRun).not.toHaveBeenCalled()
    })

    it('preserves fields on a start failure and supports retry', async () => {
        const stub = createRunService(0)
        const service = { ...stub, startRun: vi.fn(stub.startRun).mockRejectedValueOnce(new Error('Falha simulada. Tente novamente.')) }
        render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Registrar e analisar' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('Falha simulada')
        expect(screen.getByLabelText('Valor')).toHaveValue('123,45')
        fireEvent.click(screen.getByRole('button', { name: 'Registrar e analisar' }))
        await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Execução concluída'))
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('handles status failure without creating completed history', async () => {
        render(<App service={{ startRun: async () => ({ runId: 'demo' }), getRunStatus: async () => { throw new Error('Status indisponível.') } }} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Registrar e analisar' }))
        expect(await screen.findByRole('alert')).toHaveTextContent('Status indisponível')
        expect(screen.queryByRole('button', { name: 'Ver resultado: Mercado demo' })).not.toBeInTheDocument()
    })

    it('times out even when a service promise never settles', async () => {
        vi.useFakeTimers()
        const service: RunService = { startRun: () => new Promise(() => { }), getRunStatus: vi.fn() }
        render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Registrar e analisar' }))
        await act(async () => { await vi.advanceTimersByTimeAsync(10_001) })
        expect(screen.getByRole('alert')).toHaveTextContent('demorou demais')
        expect(screen.getByRole('button', { name: 'Registrar e analisar' })).toBeEnabled()
    })

    it('stops polling on unmount', async () => {
        vi.useFakeTimers()
        const service: RunService = { startRun: async () => ({ runId: 'demo' }), getRunStatus: vi.fn(async () => ({ status: 'running' as const })) }
        const { unmount } = render(<App service={service} />)
        fill()
        fireEvent.click(screen.getByRole('button', { name: 'Registrar e analisar' }))
        await act(async () => { await vi.advanceTimersByTimeAsync(100) })
        expect(service.getRunStatus).toHaveBeenCalledTimes(1)
        unmount()
        await act(async () => { await vi.advanceTimersByTimeAsync(15_000) })
        expect(service.getRunStatus).toHaveBeenCalledTimes(1)
        expect(vi.getTimerCount()).toBe(0)
    })
})