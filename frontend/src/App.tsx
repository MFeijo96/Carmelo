import { useEffect, useReducer, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, Check, ChevronRight, CircleAlert, Clock3, House, LoaderCircle, Play, ReceiptText, RefreshCw, RotateCcw, ShieldCheck } from 'lucide-react'
import { startRun, getRunStatus } from './services/runs'
import { categories, initialState, money, monthLabel, payments, parseAmount, validateInput, workflowReducer, type ExpenseInput, type RunResult, type RunService } from './workflow'

const defaultService: RunService = { startRun, getRunStatus }
const categoryLabels = { Alimentacao: 'Alimentação', Moradia: 'Moradia', Transporte: 'Transporte', Saude: 'Saúde', Educacao: 'Educação', Comunicacao: 'Comunicação', Lazer: 'Lazer', Outros: 'Outros' }
const paymentLabels = { ...payments, debito: 'Débito', credito: 'Crédito' }
const statusPresentation = {
    idle: { label: 'Crew: idle', color: '#606870' },
    running: { label: 'Crew: running', color: '#1755a6' },
    done: { label: 'Crew: done', color: '#14614d' },
    error: { label: 'Crew: error', color: '#b42318' },
} as const
const localDate = () => {
    const date = new Date()
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function Results({ result }: { result: RunResult }) {
    return <>
        <div className="result-heading"><div><span className="eyebrow">Resumo do mês</span><h3>{monthLabel(result.month)}</h3></div><span className="tag"><Check size={13} /> {statusPresentation.done.label}</span></div>
        <div className="metrics">
            <div className="metric primary"><span>Total registrado</span><strong>{money(result.totalCents)}</strong></div>
            <div className="metric"><span>Despesas</span><strong>{result.count.toString().padStart(2, '0')}</strong></div>
            <div className="metric"><span>Recorrentes</span><strong>{money(result.recurringCents)}</strong></div>
        </div>
        <div className="breakdowns">
            <div><h4>Por categoria</h4>{result.categories.map(item => <div className="category-row" key={item.name}>
                <div className="flex justify-between gap-3"><span>{categoryLabels[item.name]}</span><strong>{money(item.cents)}</strong></div>
                <div className="bar-track"><div style={{ width: `${item.cents / result.totalCents * 100}%` }} /></div>
            </div>)}</div>
            <div><h4>Por pagamento</h4>{result.payments.map(item => <div className="payment-row" key={item.name}><span>{paymentLabels[item.name]}</span><strong>{money(item.cents)}</strong></div>)}</div>
        </div>
        <div className="record"><ReceiptText size={19} /><div><span className="eyebrow">Despesa demonstrativa</span><strong>{result.input.description}</strong><span>{categoryLabels[result.input.category]} · {paymentLabels[result.input.payment]}{result.input.recurring ? ' · Recorrente' : ''}</span></div><strong>{money(result.input.amountCents)}</strong></div>
        <p className="insight">{result.count} {result.count === 1 ? 'despesa no exemplo' : 'despesas no exemplo'} em {monthLabel(result.month)}, totalizando {money(result.totalCents)}.</p>
        <p className="result-note">Dados demonstrativos fixos, independentes dos valores informados. Não constitui aconselhamento financeiro.</p>
    </>
}

export default function App({ service = defaultService }: { service?: RunService }) {
    const [state, dispatch] = useReducer(workflowReducer, initialState)
    const [formError, setFormError] = useState<string | null>(null)
    const [selectedId, setSelectedId] = useState<string | null>(null)
    const [lastUpdated, setLastUpdated] = useState(() => new Date())
    const formRef = useRef<HTMLFormElement>(null)
    const resultHeadingRef = useRef<HTMLHeadingElement>(null)
    const lastInput = useRef<ExpenseInput | null>(null)
    const locked = useRef(false)
    const running = state.phase === 'running'
    const selected = state.history.find(result => result.requestId === selectedId)
    const error = formError ?? state.error
    const displayStatus = error ? 'error' : state.phase
    const presentation = statusPresentation[displayStatus]

    useEffect(() => {
        if (state.phase !== 'running' || !state.runId || !lastInput.current) return
        const requestId = state.runId
        const input = { ...lastInput.current }
        let stopped = false
        let timer: ReturnType<typeof setTimeout> | undefined
        const fail = (cause: unknown) => {
            if (stopped) return
            setLastUpdated(new Date())
            locked.current = false
            dispatch({ type: 'failed', runId: requestId, message: cause instanceof Error ? cause.message : 'Não foi possível concluir. Tente novamente.' })
        }
        async function poll(runId: string) {
            try {
                const status = await service.getRunStatus(runId)
                if (stopped) return
                setLastUpdated(new Date())
                if (status.status === 'done') {
                    locked.current = false
                    dispatch({ type: 'completed', runId: requestId, result: status.result, input })
                    setSelectedId(requestId)
                    for (const field of ['description', 'amount']) (formRef.current?.elements.namedItem(field) as HTMLInputElement).value = ''
                } else {
                    timer = setTimeout(() => { void poll(runId) }, 400)
                }
            } catch (cause) { fail(cause) }
        }
        void service.startRun(input).then(({ runId }) => {
            if (stopped) return
            setLastUpdated(new Date())
            void poll(runId)
        }).catch(fail)
        return () => { stopped = true; clearTimeout(timer); locked.current = false }
    }, [state.phase, state.runId, service])

    useEffect(() => {
        if (selectedId) resultHeadingRef.current?.focus({ preventScroll: true })
    }, [selectedId])

    function run(input: ExpenseInput) {
        if (locked.current) return
        locked.current = true
        lastInput.current = { ...input }
        setFormError(null)
        setSelectedId(null)
        setLastUpdated(new Date())
        dispatch({ type: 'started', runId: crypto.randomUUID() })
    }

    function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        if (locked.current) return
        const data = new FormData(event.currentTarget)
        try {
            run(validateInput({
                date: String(data.get('date')), description: String(data.get('description')),
                amountCents: parseAmount(String(data.get('amount'))),
                category: String(data.get('category')) as RunResult['input']['category'],
                payment: String(data.get('payment')) as RunResult['input']['payment'],
                recurring: data.get('recurring') === 'on',
            }))
        } catch (cause) {
            setLastUpdated(new Date())
            setFormError(cause instanceof Error ? cause.message : 'Confira os campos.'); return
        }
    }

    function retry() {
        const input = lastInput.current
        const form = formRef.current
        if (!input || !form || locked.current) return
        for (const field of ['date', 'description', 'category', 'payment'] as const) {
            (form.elements.namedItem(field) as HTMLInputElement | HTMLSelectElement).value = input[field]
        }
        (form.elements.namedItem('amount') as HTMLInputElement).value = `${Math.floor(input.amountCents / 100)},${String(input.amountCents % 100).padStart(2, '0')}`
            ; (form.elements.namedItem('recurring') as HTMLInputElement).checked = input.recurring
        run(input)
    }

    function reset() {
        if (locked.current) return
        formRef.current?.reset()
        lastInput.current = null
        setFormError(null)
        setSelectedId(null)
        setLastUpdated(new Date())
        dispatch({ type: 'reset' })
            ; (formRef.current?.elements.namedItem('description') as HTMLInputElement)?.focus()
    }

    return <div className="app-shell">
        <a className="skip-link" href="#main">Ir para o conteúdo</a>
        <header className="app-header"><div className="brand"><span className="brand-mark"><House size={23} strokeWidth={1.7} /></span><span>Home Financial</span></div><span className="workspace"><span className="status-dot" /> Casa demonstrativa</span></header>
        <main id="main">
            <div className="crew-status" role="status" aria-live="polite" data-state={displayStatus}>
                <span className="crew-state" style={{ color: presentation.color }}><span className="crew-indicator" aria-hidden="true" />{presentation.label}</span>
                <span className="last-updated">Atualizado em <time dateTime={lastUpdated.toISOString()} title={lastUpdated.toLocaleString('pt-BR')}>{new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(lastUpdated)}</time></span>
            </div>
            <div className="page-title"><div><p className="eyebrow">Minha casa / Despesas</p><h1>Despesas da casa</h1></div><span className="local-badge"><ShieldCheck size={16} /> Ambiente local</span></div>
            <div className="demo-notice"><CircleAlert size={17} /><p>Modo demonstração. Use apenas dados fictícios. Os registros são apagados ao recarregar a página.</p></div>
            <div className="workbench">
                <section className="input-section" aria-labelledby="inputs-title">
                    <div className="section-heading"><span className="section-number">01</span><h2 id="inputs-title">Nova despesa</h2></div>
                    <form ref={formRef} onSubmit={submit} aria-describedby={error ? 'form-error' : undefined}>
                        <fieldset disabled={running}>
                            <div className="field"><label htmlFor="date">Data</label><input id="date" name="date" type="date" defaultValue={localDate()} required /></div>
                            <div className="field"><label htmlFor="description">Descrição</label><input id="description" name="description" placeholder="Ex.: compras do mercado" maxLength={120} required /></div>
                            <div className="field"><label htmlFor="amount">Valor</label><div className="amount-input"><span>R$</span><input id="amount" name="amount" inputMode="decimal" placeholder="0,00" aria-describedby={error ? 'form-error' : undefined} required /></div></div>
                            <div className="field"><label htmlFor="category">Categoria</label><select id="category" name="category" defaultValue="Alimentacao">{categories.map(category => <option key={category} value={category}>{categoryLabels[category]}</option>)}</select></div>
                            <div className="field"><label htmlFor="payment">Forma de pagamento</label><select id="payment" name="payment" defaultValue="debito">{Object.keys(payments).map(payment => <option key={payment} value={payment}>{paymentLabels[payment as keyof typeof payments]}</option>)}</select></div>
                            <label className="recurring"><input name="recurring" type="checkbox" /><span>Despesa recorrente</span></label>
                        </fieldset>
                        {error && <p id="form-error" className="error" role="alert">{statusPresentation.error.label}: {error}</p>}
                        <div className="run-controls">
                            {state.error && lastInput.current ? <button className="submit-button" type="button" onClick={retry}><RefreshCw size={18} />Tentar novamente<ArrowRight size={17} className="ml-auto" /></button> : <button className="submit-button" type="submit" disabled={running}>{running ? <LoaderCircle className="spin" size={18} /> : <Play size={18} />}{running ? statusPresentation.running.label : 'Executar'}<ArrowRight size={17} className="ml-auto" /></button>}
                            <button className="reset-button" type="button" onClick={reset} disabled={running} aria-label="Redefinir" title="Redefinir"><RotateCcw size={18} /></button>
                        </div>
                    </form>
                </section>
                <section className="results-section" aria-labelledby="results-title">
                    <div className="section-heading"><span className="section-number">02</span><h2 id="results-title" ref={resultHeadingRef} tabIndex={-1}>Resultados</h2><span className="muted-label">Simulação local</span></div>
                    {selected ? <Results result={selected} /> : <div className="empty-result"><span className={`empty-icon ${running ? 'is-running' : ''}`}>{running ? <LoaderCircle className="spin" size={32} /> : <ReceiptText size={34} strokeWidth={1.3} />}</span><h3>{running ? statusPresentation.running.label : 'Nenhuma análise por aqui'}</h3><p>{running ? 'Aguardando o resultado da execução.' : 'Nenhuma despesa registrada nesta sessão.'}</p><div className="empty-ledger" aria-hidden="true"><span /><span /><span /></div></div>}
                </section>
            </div>
            <section className="history-section" aria-labelledby="history-title">
                <div className="section-heading"><span className="section-number">03</span><h2 id="history-title">Histórico</h2><span className="muted-label">{state.history.length} {state.history.length === 1 ? 'execução' : 'execuções'}</span></div>
                {state.history.length === 0 ? <div className="history-empty"><Clock3 size={18} /><span>Nenhuma execução concluída nesta sessão.</span></div> : <ul className="history-list">{state.history.map(result => <li key={result.requestId}><button type="button" className={`history-row ${selectedId === result.requestId ? 'selected' : ''}`} disabled={running} aria-label={`Ver resultado: ${result.submittedInput.description}`} aria-pressed={selectedId === result.requestId} onClick={() => setSelectedId(result.requestId)}><span className="history-icon"><ReceiptText size={18} /></span><span className="history-description"><strong>{result.submittedInput.description}</strong><span>{monthLabel(result.submittedInput.date.slice(0, 7))}</span></span><span className="history-amount">{money(result.submittedInput.amountCents)}</span><span className="history-status"><Check size={13} /> {statusPresentation.done.label}</span><ChevronRight size={17} /></button></li>)}</ul>}
            </section>
            <footer><span>Home Financial</span><span>Dados fictícios · Sem conexão bancária</span></footer>
        </main>
    </div>
}