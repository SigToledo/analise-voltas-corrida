// Etiqueta do STATUS oficial do piloto (ex.: DQ = desclassificado), como está
// no resumo oficial. Vermelha: desclassificação muda o resultado e precisa
// saltar aos olhos. Os tempos do piloto continuam os do PDF.

const SIGNIFICADO: Record<string, string> = {
  DQ: 'Desclassificado no resultado oficial',
  DSQ: 'Desclassificado no resultado oficial',
}

export function StatusOficial({ status }: { status: string }) {
  return (
    <span
      className="status-oficial"
      title={SIGNIFICADO[status] ?? `Status no resultado oficial: ${status}`}
    >
      {status}
    </span>
  )
}
