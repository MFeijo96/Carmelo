import { useEffect, useReducer, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, Check, ChevronRight, CircleAlert, Clock3, House, LoaderCircle, Plus, ReceiptText, ShieldCheck } from 'lucide-react'
import { startRun, getRunStatus } from './services/runs'
import { categories, initialState, money, monthLabel, payments, parseAmount, validateInput, workflowReducer, type RunResult, type RunService } from './workflow'

const defaultService: RunService = { startRun, getRunStatus }
const categoryLabels = { Alimentacao: 'Alimentação', Moradia: 'Moradia', Transporte: 'Transporte', Saude: 'Saúde', Educacao: 'Educação', Comunicacao: 'Comunicação', Lazer: 'Lazer', Outros: 'Outros' }
const paymentLabels = { ...payments, debito: 'Débito', credito: 'Crédito' }
const localDate = () => {
    const date = new Date()
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function interruptible<Value>(promise: Promise<Value>, signal: AbortSignal): Promise<Value> {
    return new Promise((resolve, reject) => {
        const abort = () => reject(signal.reason)
        if (signal.aborted) { reject(signal.reason); return }
        signal.addEventListener('abort', abort, { once: true })
        promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort))
    })
}

function pause(signal: AbortSignal): Promise<void> {
    return new Promise((resolve, reject) => {
        const abort = () => { clearTimeout(timer); reject(signal.reason) }
        const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, 400)
        signal.addEventListener('abort', abort, { once: true })
        if (signal.aborted) { signal.removeEventListener('abort', abort); abort() }
    })
}

function Results({ result }: { result: RunResult }) {
    return <>
        <div className="result-heading"><div><span className="eyebrow">Resumo do mês</span><h3>{monthLabel(result.month)}</h3></div><span className="tag"><Check size={13} /> Concluído</span></div>
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
        <div className="record"><ReceiptText size={19} /><div><span className="eyebrow">Despesa desta execução</span><strong>{result.input.description}</strong><span>{categoryLabels[result.input.category]} · {paymentLabels[result.input.payment]}{result.input.recurring ? ' · Recorrente' : ''}</span></div><strong>{money(result.input.amountCents)}</strong></div>
        <p className="insight">{result.count} {result.count === 1 ? 'despesa registrada' : 'despesas registradas'} em {monthLabel(result.month)}, totalizando {money(result.totalCents)}. A categoria é a que você selecionou.</p>
        <p className="result-note">Resultado simulado e educativo. Não constitui aconselhamento financeiro.</p>
    </>
}

export default function App({ service = defaultService }: { service?: RunService }) {
    const [state, dispatch] = useReducer(workflowReducer, initialState)
    const [formError, setFormError] = useState<string | null>(null)
    const [selectedId, setSelectedId] = useState<string | null>(null)
    const formRef = useRef<HTMLFormElement>(null)
    const resultHeadingRef = useRef<HTMLHeadingElement>(null)
    const active = useRef<AbortController | null>(null)
    const mounted = useRef(true)
    const locked = useRef(false)
    const running = state.phase === 'running'
    const selected = state.history.find(result => result.runId === selectedId)
    const error = formError ?? state.error

    useEffect(() => {
        mounted.current = true
        return () => { mounted.current = false; active.current?.abort(new Error('Execução interrompida.')) }
    }, [])

    useEffect(() => {
        if (selectedId) resultHeadingRef.current?.focus({ preventScroll: true })
    }, [selectedId])

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        if (locked.current) return
        const form = event.currentTarget
        const data = new FormData(form)
        let input
        try {
            input = validateInput({
                date: String(data.get('date')), description: String(data.get('description')),
                amountCents: parseAmount(String(data.get('amount'))),
                category: String(data.get('category')) as RunResult['input']['category'],
                payment: String(data.get('payment')) as RunResult['input']['payment'],
                recurring: data.get('recurring') === 'on',
            })
        } catch (cause) {
            setFormError(cause instanceof Error ? cause.message : 'Confira os campos.'); return
        }
        locked.current = true
        setFormError(null)
        setSelectedId(null)
        const requestId = crypto.randomUUID()
        dispatch({ type: 'started', runId: requestId })
        const controller = new AbortController()
        active.current = controller
        const timeout = setTimeout(() => controller.abort(new Error('A execução demorou demais. Tente novamente.')), 10_000)
        try {
            const { runId } = await interruptible(service.startRun(input), controller.signal)
            while (!controller.signal.aborted) {
                const status = await interruptible(service.getRunStatus(runId), controller.signal)
                if (status.status === 'done') {
                    if (!mounted.current) return
                    dispatch({ type: 'completed', runId: requestId, result: status.result })
                    setSelectedId(status.result.runId)
                    for (const field of ['description', 'amount']) (form.elements.namedItem(field) as HTMLInputElement).value = ''
                    return
                }
                await pause(controller.signal)
            }
        } catch (cause) {
            if (mounted.current) dispatch({ type: 'failed', runId: requestId, message: cause instanceof Error ? cause.message : 'Não foi possível concluir. Tente novamente.' })
        } finally {
            clearTimeout(timeout)
            locked.current = false
            active.current = null
        }
    }

    return <div className="app-shell">
        <a className="skip-link" href="#main">Ir para o conteúdo</a>
        <header className="app-header"><div className="brand"><span className="brand-mark"><House size={23} strokeWidth={1.7} /></span><span>Home Financial</span></div><span className="workspace"><span className="status-dot" /> Casa demonstrativa</span></header>
        <main id="main">
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
                        {error && <p id="form-error" className="error" role="alert">{error}</p>}
                        <button className="submit-button" type="submit" disabled={running}>{running ? <LoaderCircle className="spin" size={18} /> : <Plus size={18} />}{running ? 'Processando...' : 'Registrar e analisar'}{!running && <ArrowRight size={17} className="ml-auto" />}</button>
                        <div className="run-status" role="status" aria-live="polite"><span className={`status-dot ${running ? 'pulse' : ''}`} />{running ? 'Execução em andamento' : state.phase === 'done' ? 'Execução concluída' : 'Pronto para registrar'}</div>
                    </form>
                </section>
                <section className="results-section" aria-labelledby="results-title">
                    <div className="section-heading"><span className="section-number">02</span><h2 id="results-title" ref={resultHeadingRef} tabIndex={-1}>Resultados</h2><span className="muted-label">Simulação local</span></div>
                    {selected ? <Results result={selected} /> : <div className="empty-result"><span className={`empty-icon ${running ? 'is-running' : ''}`}>{running ? <LoaderCircle className="spin" size={32} /> : <ReceiptText size={34} strokeWidth={1.3} />}</span><h3>{running ? 'Organizando a despesa' : 'Nenhuma análise por aqui'}</h3><p>{running ? 'Aguardando o resultado da execução.' : 'Nenhuma despesa registrada nesta sessão.'}</p><div className="empty-ledger" aria-hidden="true"><span /><span /><span /></div></div>}
                </section>
            </div>
            <section className="history-section" aria-labelledby="history-title">
                <div className="section-heading"><span className="section-number">03</span><h2 id="history-title">Histórico</h2><span className="muted-label">{state.history.length} {state.history.length === 1 ? 'execução' : 'execuções'}</span></div>
                {state.history.length === 0 ? <div className="history-empty"><Clock3 size={18} /><span>Nenhuma execução concluída nesta sessão.</span></div> : <ul className="history-list">{state.history.map(result => <li key={result.runId}><button type="button" className={`history-row ${selectedId === result.runId ? 'selected' : ''}`} disabled={running} aria-label={`Ver resultado: ${result.input.description}`} aria-pressed={selectedId === result.runId} onClick={() => setSelectedId(result.runId)}><span className="history-icon"><ReceiptText size={18} /></span><span className="history-description"><strong>{result.input.description}</strong><span>{monthLabel(result.month)} · {new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date(result.completedAt))}</span></span><span className="history-amount">{money(result.input.amountCents)}</span><span className="history-status"><Check size={13} /> Concluído</span><ChevronRight size={17} /></button></li>)}</ul>}
            </section>
            <footer><span>Home Financial</span><span>Dados fictícios · Sem conexão bancária</span></footer>
        </main>
    </div>
}