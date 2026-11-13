# Higgsfield prompt style - FOLLOW THIS EXACTLY

## How clips are remade
We do NOT generate a new still image and animate it. He gives Higgsfield (Wan 3.0 ONLY):
- `@video1` = the original clip (one clip per generation in this pipeline)
- `@image1`, `@image2`, ... = character photos the user picked (from `references/characters/`)
- the last `@imageN` = the product photo (from `references/product/`)
and one structured prompt that says: recreate @video1 frame by frame, keep every movement, and change
ONLY the people, clothes colours and background. Nothing else.

## References
- `references/characters/` - The user's character photos, as loose files. The file name describes the person:
  `20-woman-2.jpg` = woman in her 20s, `20-men.jpg` = man in his 20s, `30-woman-2.png` = woman in her 30s,
  `50-woman.png` = woman in her 50s, `old-woman.jpg` = elderly woman, `woman-b.jpg` / `20-woman-b-2.jpg` =
  another set of women. Files with the same base name (e.g. `20-woman-b-2` and `20-woman-b-3`) may be the
  SAME person - Read them to check, and when they are, upload both as references for that person.
  Pick by matching each person in the clip: same gender and similar age range as the original person.
  Read the photo before choosing it.
  The MAIN character (the person wearing/holding the bag) is the SAME photo in every clip of the video.
  Side characters get other photos, and never the main character's photo. Try not to reuse the same main
  character as the previous job (check earlier `jobs/*/prompts/*.json`) so videos look different.
  If no photo fits a person (e.g. a child, or more people than photos), stop and ask the user.
  Write in each prompt file which file you used for which person (key "character_files").
- `references/product/` - the product photo. Always the LAST @image.
- Number the @images per clip in the order you upload them, and name in each clip's prompt
  exactly which @image is which.

## Product block
Use the "Product block" from `notes/product.md` (it changes per product).

## Prompt template (one clip)
```
Recreate @video1 frame by frame. It starts and ends on exactly the same frame as @video1 and keeps exactly the same length and timing. Only make the changes below.

MOVEMENTS (highest priority): every movement must be EXACTLY THE SAME as in @video1, frame by frame. This includes every person's hand, arm, head and body movement, every step, gesture and facial expression, and the movement of every object, including the product. Every camera movement, zoom and angle stays the same, with the same speed, direction, distance and path. Do not add, remove, speed up, slow down or change any movement.

PRODUCT: it looks exactly like the product in @imageN: same shape, material, colors and details. <Product block from notes/product.md>. It is a solid, lifeless object: it never trembles, shakes, vibrates, jitters, flickers or wobbles. When nobody touches it, it stays perfectly still. When a person moves it, it moves only together with their hands or body, smoothly, exactly as in @video1. If it has a face, eyes, ears or legs, they never move on their own, it does not blink or breathe, and no part of it detaches or changes.

CHANGES:
1. Replace the <describe the person in @video1, e.g. "woman holding the product"> with the <woman/man> from @image1. Keep her face, hair, skin tone and body exactly as in @image1. She wears the same type of clothes as in @video1, in new colors: <top> becomes <new colour>, <bottom> becomes <new colour>.
2. <next person -> @image2, same wording>
3. Change the background: <specific, natural for the action: walls, floor, furniture, light, time of day>. No shop names, signs or logos. It looks natural and realistic.
Everything else stays exactly as in @video1.

TEXT: remove all text and emojis: captions, subtitles, stickers, logos, watermarks and any signs with writing. The final video has no text, logos or brand designs anywhere.

Do not add any new objects, people or text. Do not change the clip's length or timing. Do not change anything except what is described above. Nothing should look strange or unnatural. Do not change the product's colours. Do not deform the product, or anyone's hands or face.
```

## Extra rules
- If the original shows a different version of the product (other colour/model, or a competitor's product), add: "Replace the <original product> with the product from @imageN, same size and position."
- Uniforms / work clothes that define the scene (police, staff) stay exactly as in @video1 unless the user says otherwise; only the faces change.
- Clothes: keep the TYPE of clothing, change only the COLOURS (muted, realistic colours: taupe, chocolate brown, olive, charcoal, burgundy, sage...).
- White blur patches in the source are not part of the scene - say: "Some areas of @video1 are covered with white blur patches. Do not copy them; in those areas show <what belongs there>."
- Brand items (store logos, branded boxes, known characters like Disney) -> describe a plain unbranded version. If Higgsfield returns "Protected content", blur/replace that item and retry.
- Never put the text hook in the prompt - it is added later in the edit.
- One prompt per clip. Clips that are continuations of each other (same shot split by a cut) use the same people, clothes and background, and say so: "This clip continues the previous clip ...".
