let currentSpeakAbort = null;

export async function speakText(fullText) {
  const endpoint = `${import.meta.env.VITE_API_URL}/speak`;

  // Setup abort controller
  if (currentSpeakAbort) currentSpeakAbort.abort();
  const abort = { aborted: false, abort: () => (abort.aborted = true) };
  currentSpeakAbort = abort;

  // Step 1: Split text
  const splitRes = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: fullText, split: true }),
  });

  if (!splitRes.ok) {
    console.error("Failed to split text:", await splitRes.text());
    return;
  }

  const { sentences } = await splitRes.json();
  const buffer = [];
  let i = 0;

  // Step 2: Preload initial buffer (up to 3)
  while (buffer.length < 3 && i < sentences.length) {
    const blob = await fetchAudioBlob(sentences[i++], endpoint);
    if (blob) buffer.push(blob);
  }

  // Step 3: Play while maintaining the 3-blob buffer
  while (buffer.length > 0 && !abort.aborted) {
    const currentBlob = buffer.shift();

    // Start fetching the next blob while playing
    const nextBlobPromise =
      i < sentences.length ? fetchAudioBlob(sentences[i++], endpoint) : Promise.resolve(null);

    await playAudioBlob(currentBlob, abort);

    const nextBlob = await nextBlobPromise;
    if (nextBlob) buffer.push(nextBlob);
  }
}

export function stopSpeaking() {
  if (currentSpeakAbort) currentSpeakAbort.abort();
}

async function fetchAudioBlob(sentence, endpoint) {
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: sentence }),
    });
    if (!response.ok) {
      console.error("TTS error:", await response.text());
      return null;
    }
    return await response.blob();
  } catch (err) {
    console.error("TTS fetch error:", err);
    return null;
  }
}

function playAudioBlob(blob, abort) {
  return new Promise((resolve) => {
    if (abort.aborted) return resolve();
    const audio = new Audio(URL.createObjectURL(blob));

    const cleanUp = () => {
      audio.pause();
      audio.src = "";
      resolve();
    };

    audio.onended = cleanUp;
    audio.onerror = cleanUp;
    audio.play();

    const interval = setInterval(() => {
      if (abort.aborted) {
        clearInterval(interval);
        cleanUp();
      }
    }, 100);
  });
}
