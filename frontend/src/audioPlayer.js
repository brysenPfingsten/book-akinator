export async function speakText(fullText) {
    const endpoint = `${import.meta.env.VITE_API_URL}/speak`
    // 1. Split the chapter into sentences
    const splitRes = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: fullText, split: true })
    });
  
    if (!splitRes.ok) {
      console.error("Failed to split text:", await splitRes.text());
      return;
    }
  
    const { sentences } = await splitRes.json();
  
    // 2. For each sentence, fetch and play audio
    for (const sentence of sentences) {
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: sentence })
        });
  
        if (!response.ok) {
          console.error("TTS error:", await response.text());
          continue;
        }
  
        const blob = await response.blob();
        const audioUrl = URL.createObjectURL(blob);
  
        await new Promise((resolve) => {
          const audio = new Audio(audioUrl);
          audio.onended = resolve;
          audio.onerror = () => {
            console.error("Audio playback failed");
            resolve();
          };
          audio.play();
        });
      } catch (err) {
        console.error("TTS request failed:", err);
      }
    }
  }