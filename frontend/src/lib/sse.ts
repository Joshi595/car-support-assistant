/** Read Server-Sent Events from a fetch response (EventSource cannot POST a JSON body). */
export type SseEvent = { event: string; data: unknown };

export async function* readEvents(response: Response): AsyncGenerator<SseEvent> {
  if (!response.body) return;
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const event = /^event: (.*)$/m.exec(block)?.[1] ?? "message";
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (data !== undefined) yield { event, data: JSON.parse(data) };
    }
  }
}
