import { useState, type FormEvent } from 'react'

import {
  errorMessage,
  useCreateExpense,
  type Expense,
  type Member,
  type Store,
} from '../api/queries'
import { formatCents, formatDate, parseEuro, todayIso } from '../lib/money'
import { Modal } from './Modal'

type Defaults = { storeId: string; buyerId: string; bookingDate: string }

/**
 * Enter one receipt after the other: each saved receipt is listed as a
 * summary and a fresh form appears for the next one.
 */
export function ExpenseModal({
  members,
  stores,
  defaultBuyerId,
  onManageStores,
  onClose,
}: {
  members: Member[]
  stores: Store[]
  defaultBuyerId: string
  onManageStores: () => void
  onClose: () => void
}) {
  const [saved, setSaved] = useState<Expense[]>([])
  const [defaults, setDefaults] = useState<Defaults>({
    storeId: '',
    buyerId: defaultBuyerId,
    bookingDate: todayIso(),
  })

  return (
    <Modal
      title="Ausgaben erfassen"
      onClose={onClose}
      footer={
        <button type="submit" className="button">
          Fertig
        </button>
      }
    >
      {saved.length > 0 && (
        <ul className="saved-receipts" aria-label="Gespeicherte Kassenzettel">
          {saved.map((e) => (
            <li key={e.id}>
              <span aria-hidden="true">✓</span> {e.store.name} · {formatCents(e.amount_cents)} ·{' '}
              {formatDate(e.booking_date)}
            </li>
          ))}
        </ul>
      )}

      {stores.length === 0 ? (
        <div className="empty-hint">
          <p>Lege zuerst ein Geschäft an, z. B. deinen Supermarkt.</p>
          <button type="button" className="button primary" onClick={onManageStores}>
            Geschäfte verwalten
          </button>
        </div>
      ) : (
        // New key → fresh, empty form for the next receipt
        <ExpenseForm
          key={saved.length}
          members={members}
          stores={stores}
          defaults={defaults}
          onSaved={(e) => {
            setSaved((prev) => [...prev, e])
            // Buyer and date usually stay the same within a stack of receipts
            setDefaults({ storeId: '', buyerId: e.buyer_id, bookingDate: e.booking_date })
          }}
        />
      )}
    </Modal>
  )
}

function ExpenseForm({
  members,
  stores,
  defaults,
  onSaved,
}: {
  members: Member[]
  stores: Store[]
  defaults: Defaults
  onSaved: (expense: Expense) => void
}) {
  const createExpense = useCreateExpense()
  const [storeId, setStoreId] = useState(defaults.storeId)
  const [buyerId, setBuyerId] = useState(defaults.buyerId)
  const [price, setPrice] = useState('')
  const [shares, setShares] = useState<Record<string, string>>({})
  const [bookingDate, setBookingDate] = useState(defaults.bookingDate)

  const priceCents = parseEuro(price)
  const shareCents = members.map((m) => ({
    member_id: m.id,
    amount_cents: parseEuro(shares[m.id] ?? ''),
  }))
  const sharesValid = shareCents.every((s) => s.amount_cents !== null)
  const sharedCents =
    priceCents !== null && sharesValid
      ? priceCents - shareCents.reduce((sum, s) => sum + (s.amount_cents ?? 0), 0)
      : null

  const error =
    priceCents === null
      ? 'Ungültiger Preis'
      : !sharesValid
        ? 'Ungültiger Betrag bei einem Anteil'
        : sharedCents !== null && sharedCents < 0
          ? 'Persönliche Anteile übersteigen den Preis'
          : null

  const canSubmit =
    storeId !== '' &&
    buyerId !== '' &&
    bookingDate !== '' &&
    priceCents !== null &&
    priceCents > 0 &&
    error === null &&
    !createExpense.isPending

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    createExpense.mutate(
      {
        store_id: storeId,
        buyer_id: buyerId,
        amount_cents: priceCents,
        booking_date: bookingDate,
        shares: shareCents.flatMap((s) =>
          s.amount_cents ? [{ member_id: s.member_id, amount_cents: s.amount_cents }] : [],
        ),
      },
      { onSuccess: onSaved },
    )
  }

  return (
    <form className="expense-form" onSubmit={handleSubmit} aria-label="Kassenzettel">
      <label>
        Geschäft
        <select value={storeId} onChange={(e) => setStoreId(e.target.value)} autoFocus required>
          <option value="" disabled>
            Bitte wählen …
          </option>
          {stores.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Käufer
        <select value={buyerId} onChange={(e) => setBuyerId(e.target.value)} required>
          {members.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
            </option>
          ))}
        </select>
      </label>

      <label>
        Preis (€)
        <input
          inputMode="decimal"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          placeholder="0,00"
          required
        />
      </label>

      <label>
        Buchungsdatum
        <input
          type="date"
          value={bookingDate}
          onChange={(e) => setBookingDate(e.target.value)}
          required
        />
      </label>

      <fieldset className="shares">
        <legend>Persönliche Anteile</legend>
        {members.map((m) => (
          <label key={m.id}>
            {m.display_name} (€)
            <input
              inputMode="decimal"
              value={shares[m.id] ?? ''}
              onChange={(e) => setShares((prev) => ({ ...prev, [m.id]: e.target.value }))}
              placeholder="0,00"
            />
          </label>
        ))}
        <div className="computed">
          <span>Geteilt</span>
          <output aria-live="polite">
            {sharedCents !== null && sharedCents >= 0 && priceCents ? (
              <>
                {formatCents(sharedCents)}
                {members.length > 1 && (
                  <small> (je {formatCents(sharedCents / members.length)})</small>
                )}
              </>
            ) : (
              '–'
            )}
          </output>
        </div>
      </fieldset>

      {error && (price !== '' || !sharesValid) && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {createExpense.isError && (
        <p role="alert" className="form-error">
          {errorMessage(createExpense.error, 'Speichern fehlgeschlagen.')}
        </p>
      )}

      <button type="submit" className="button primary" disabled={!canSubmit}>
        {createExpense.isPending ? 'Speichert …' : 'Speichern & nächster Zettel'}
      </button>
    </form>
  )
}
