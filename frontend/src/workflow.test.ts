import { afterEach, describe, expect, it, vi } from 'vitest'
import { initialState, parseAmount, validateInput, workflowReducer, type ExpenseInput } from './workflow'
import { createRunService } from './services/runs'

const input: ExpenseInput = { date: '2026-10-09', description: 'Mercado demo', amountCents: 12345, category: 'Alimentacao', payment: 'debito', recurring: false }
afterEach(() => vi.useRealTimers())

describe('BRL and input validation (AC-P0.3.1/.2/.3/.5)', () => {
    it.each([['1.234,56', 123456], ['0,01', 1], ['12,3', 1230], [' 10 ', 1000], ['999.999,99', 99999999]])('parses %s into cents', (value, cents) => {
        expect(parseAmount(value)).toBe(cents)
    })
    it.each(['0', '-1', '1.23', '1,234', 'abc', '1e3', '1000000', '', '1.23,45'])('rejects %s', value => {
        expect(() => parseAmount(value)).toThrow()
    })
    it('validates dates, description, amount, category and payment', () => {
        expect(validateInput({ ...input, description: ' Demo ' }).description).toBe('Demo')
        expect(() => validateInput({ ...input, date: '2026-02-30' })).toThrow()
        expect(() => validateInput({ ...input, description: ' ' })).toThrow()
        expect(() => validateInput({ ...input, amountCents: 1.5 })).toThrow()
        expect(() => validateInput({ ...input, payment: 'pix' as ExpenseInput['payment'] })).toThrow()
        expect(() => validateInput({ ...input, category: 'unknown' as ExpenseInput['category'] })).toThrow()
    })
})

describe('stub run service', () => {
    it('returns running then done, snapshots inputs, and makes polling idempotent', async () => {
        vi.useFakeTimers()
        const service = createRunService()
        const expense = { ...input }
        const { runId } = await service.startRun(expense)
        expense.amountCents = 99
        expect(await service.getRunStatus(runId)).toEqual({ status: 'running' })
        vi.advanceTimersByTime(1200)
        const done = await service.getRunStatus(runId)
        expect(done.status).toBe('done')
        if (done.status !== 'done') throw new Error('Expected completion')
        expect(done.result.totalCents).toBe(12345)
        done.result.totalCents = 0
        const again = await service.getRunStatus(runId)
        expect(again.status === 'done' && again.result.totalCents).toBe(12345)
        await expect(service.getRunStatus('missing')).rejects.toThrow()
        await expect(service.startRun({ ...input, amountCents: 0 })).rejects.toThrow()
    })
    it('aggregates completed expenses by month/category/payment/recurrence using cents', async () => {
        const service = createRunService(0)
        const first = await service.startRun({ ...input, amountCents: 10 })
        await service.getRunStatus(first.runId)
        const second = await service.startRun({ ...input, category: 'Moradia', payment: 'credito', amountCents: 20, recurring: true })
        expect(second.runId).not.toBe(first.runId)
        const status = await service.getRunStatus(second.runId)
        expect(status.status === 'done' && status.result).toMatchObject({ totalCents: 30, count: 2, recurringCents: 20, categories: [{ name: 'Alimentacao', cents: 10 }, { name: 'Moradia', cents: 20 }], payments: [{ name: 'debito', cents: 10 }, { name: 'credito', cents: 20 }] })
        const nextMonth = await service.startRun({ ...input, date: '2026-11-01' })
        const next = await service.getRunStatus(nextMonth.runId)
        expect(next.status === 'done' && next.result.count).toBe(1)
        const original = await service.getRunStatus(first.runId)
        expect(original.status === 'done' && original.result.totalCents).toBe(10)
    })
})

describe('workflow FSM', () => {
    it('guards transitions and stale results, and supports next entry and retry', async () => {
        const service = createRunService(0)
        const { runId } = await service.startRun(input)
        const status = await service.getRunStatus(runId)
        if (status.status !== 'done') throw new Error('Expected completion')
        const completed = { type: 'completed', runId, result: status.result } as const
        expect(workflowReducer(initialState, completed)).toBe(initialState)
        const running = workflowReducer(initialState, { type: 'started', runId })
        expect(running.phase).toBe('running')
        expect(workflowReducer(running, { type: 'started', runId: 'duplicate' })).toBe(running)
        expect(workflowReducer(running, { type: 'reset' })).toBe(running)
        expect(workflowReducer(running, { type: 'completed', runId: 'stale', result: status.result })).toBe(running)
        expect(workflowReducer(running, { type: 'failed', runId: 'stale', message: 'error' })).toBe(running)
        const done = workflowReducer(running, completed)
        expect(done.phase).toBe('done')
        expect(done.history).toHaveLength(1)
        expect(workflowReducer(done, completed)).toBe(done)
        expect(workflowReducer(done, { type: 'reset' }).phase).toBe('idle')
        const retry = workflowReducer(done, { type: 'started', runId: 'next' })
        const failed = workflowReducer(retry, { type: 'failed', runId: 'next', message: 'Tente novamente.' })
        expect(failed).toMatchObject({ phase: 'idle', error: 'Tente novamente.' })
        expect(failed.history).toHaveLength(1)
        expect(workflowReducer(failed, { type: 'started', runId: 'retry' }).error).toBeNull()
    })
})