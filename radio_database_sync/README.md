# Radio Database Sync #
Scripts that update audio metadata based on a folder structure.


## Strucutre ##

The primary structure for our "radio database" is the following folder structure, where each folder represents an audio tag that we write to the audio file's metadata: 
- Label
  - Language
    - #Unsorted
    - Genre
      - #Archive

For example, our Te Hiku Radio folder would look like this,

- 📁 Music
  - 📁 Māori
    - 📁 Country
      - 📁 #Archive
      - 🎵 Te Arikinui.mp3
      - 🎵 Kia Ora.mp3
    - 📁 Pop
    - 📁 Reggae
  - 📁 Hawaiian
  - 📁 English
- 📁 Station ID
  - 📁 Māori
    - 📁 Celebreties
      - 📁 #Archive
      - 🎵 Riki Harawira ID.mp3
      - 🎵 Maisey Rika ID.mp3
    - 📁 Haukāinga
        - 📁 #Archive
          - 🎵 Keoni ID.mp3
        - 🎵 Aunty Leni ID.mp3
  - 📁 English

## Writing Metadata ##
Scripts will take the folder structure above and use that to write metadata to the files. This allows us to control how we use smartblocks to build our playlists.

For example, the song `🎵 Kia Ora.mp3` will have the following tags updated by our scripts:
- [language] = Māori
- [genre] = Country
- [label] = Music

Any file that has a parent directory with the `#` in the name will have that added to their label. For example, `🎵 Keoni ID.mp3`:
- [language] = Māori
- [genre] = Haukāinga
- [label] = Station ID, #Archived

We will use this to exclude files with `label contains #` from our playout.