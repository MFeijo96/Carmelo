import { afterEach, describe, expect, it, vi } from 'vitest'
import { initialState, parseAmount, validateInput, workflowReducer, type ExpenseInput } from './workflow'
import { createRunService } from './services/runs'

const input: ExpenseInput = { date: '2026-10-09', description: 'Mercado demo', amountCents: 12345, category: 'category-mercado', payment: 'debito', recurring: false }
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
    it('accepts automatic categorization without treating it as a stored category', () => {
        expect(validateInput({ ...input, category: '' }, []).category).toBe('')
        expect(() => validateInput({ ...input, category: 'unknown' }, [])).toThrow()
    })
})

describe('stub run service', () => {
    it('returns fixed running/done payloads and isolated result copies', async () => {
        vi.useFakeTimers()
        const service = createRunService()
        await expect(service.getRunStatus('demo-run')).rejects.toThrow()
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
    it('returns identical mock payloads regardless of valid inputs or earlier runs', async () => {
        const service = createRunService(0)
        const first = await service.startRun({ ...input, amountCents: 10 })
        const firstStatus = await service.getRunStatus(first.runId)
        const second = await service.startRun({ ...input, date: '2026-11-01', category: 'category-moradia', payment: 'credito', amountCents: 20, recurring: true })
        expect(second).toEqual(first)
        expect(second).toEqual({ runId: 'demo-run' })
        expect(await service.getRunStatus(second.runId)).toEqual(firstStatus)
        expect(firstStatus.status === 'done' && firstStatus.result).toMatchObject({ totalCents: 12345, count: 1, recurringCents: 0, month: '2026-10' })
        await expect(service.getRunStatus('missing')).rejects.toThrow()
    })
})

describe('workflow FSM', () => {
    it('guards transitions and stale results, and supports next entry and retry', async () => {
        const service = createRunService(0)
        const { runId } = await service.startRun(input)
        const status = await service.getRunStatus(runId)
        if (status.status !== 'done') throw new Error('Expected completion')
        const completed = { type: 'completed', runId, result: status.result, input } as const
        expect(workflowReducer(initialState, completed)).toBe(initialState)
        const running = workflowReducer(initialState, { type: 'started', runId })
        expect(running.phase).toBe('running')
        expect(workflowReducer(running, { type: 'started', runId: 'duplicate' })).toBe(running)
        expect(workflowReducer(running, { type: 'reset' })).toBe(running)
        expect(workflowReducer(running, { ...completed, runId: 'stale' })).toBe(running)
        expect(workflowReducer(running, { type: 'failed', runId: 'stale', message: 'error' })).toBe(running)
        const done = workflowReducer(running, completed)
        expect(done.phase).toBe('done')
        expect(done.history).toHaveLength(1)
        expect(done.history[0].submittedInput).toEqual(input)
        expect(done.history[0].requestId).toBe(runId)
        const lateRestore = workflowReducer(done, {
            type: 'restored', results: [
                { ...status.result, input: { ...input, description: 'Stale stored value' } },
                { ...status.result, runId: 'older-expense' },
            ]
        })
        expect(lateRestore.history).toHaveLength(2)
        expect(lateRestore.history[0]).toEqual(done.history[0])
        expect(lateRestore.phase).toBe('done')
        const duringRun = workflowReducer(running, { type: 'restored', results: [status.result] })
        expect(duringRun.phase).toBe('running')
        expect(duringRun.runId).toBe(runId)
        expect(workflowReducer(done, completed)).toBe(done)
        const reset = workflowReducer(done, { type: 'reset' })
        expect(reset.phase).toBe('idle')
        expect(reset.history).toEqual(done.history)
        const retry = workflowReducer(done, { type: 'started', runId: 'next' })
        const failed = workflowReducer(retry, { type: 'failed', runId: 'next', message: 'Tente novamente.' })
        expect(failed).toMatchObject({ phase: 'idle', error: 'Tente novamente.' })
        expect(failed.history).toHaveLength(1)
        expect(workflowReducer(failed, { type: 'started', runId: 'retry' }).error).toBeNull()
    })
})