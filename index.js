const Discord = require("discord.js");
const dotenv = require("dotenv");
const { REST } = require("@discordjs/rest");
const { Routes } = require("discord-api-types/v9");
const fs = require("fs");
const { Player } = require("discord-player");
const welcomeImage = require("./image");
const byeImage = require("./image");

dotenv.config();

const TOKEN = process.env.TOKEN;

const LOAD_SLASH = process.argv[2] == "load";

const CLIENT_ID = process.env.BOT;
const GUILD_ID = process.env.GUILD;

const client = new Discord.Client({
  intents: [
    "GUILDS",
    "GUILD_MEMBERS",
    "GUILD_BANS",
    "GUILD_EMOJIS_AND_STICKERS",
    "GUILD_INTEGRATIONS",
    "GUILD_WEBHOOKS",
    "GUILD_INVITES",
    "GUILD_VOICE_STATES",
    "GUILD_PRESENCES",
    "GUILD_MESSAGES",
    "GUILD_MESSAGE_REACTIONS",
    "GUILD_MESSAGE_TYPING",
    "DIRECT_MESSAGES",
    "DIRECT_MESSAGE_REACTIONS",
    "DIRECT_MESSAGE_TYPING",
    "GUILD_SCHEDULED_EVENTS",
  ],
  partials: ["CHANNEL", "USER"],
});

const welcomeChannelId = "1043780857808293979";

client.slashcommands = new Discord.Collection();
client.player = new Player(client, {
  ytdlOptions: {
    quality: "highestaudio",
    highWaterMark: 1 << 25,
  },
});

let commands = [];

var removeByAttr = function (arr, attr, value) {
  var i = arr.length;
  while (i--) {
    if (
      arr[i] &&
      arr[i].hasOwnProperty(attr) &&
      arguments.length > 2 &&
      arr[i][attr] === value
    ) {
      arr.splice(i, 1);
    }
  }
  return arr;
};

const slashFiles = fs
  .readdirSync("./src/slash")
  .filter((file) => file.endsWith(".js"));
for (const file of slashFiles) {
  const slashcmd = require(`./src/slash/${file}`);
  client.slashcommands.set(slashcmd.data.name, slashcmd);
  if (LOAD_SLASH) commands.push(slashcmd.data.toJSON());
}

if (LOAD_SLASH) {
  const rest = new REST({ version: "9" }).setToken(TOKEN);
  console.log("Deploying slash commands");
  rest
    .put(Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID), {
      body: commands,
    })
    .then(() => {
      console.log("Successfully loaded");
      process.exit(0);
    })
    .catch((err) => {
      if (err) {
        console.log(err);
        process.exit(1);
      }
    });
} else {
  client.on("ready", () => {
    console.log(`Logged in as ${client.user.tag}`);
    client.user.setActivity("FIFA 23");
  });
  client.on("guildMemberAdd", async (member) => {
    const img = await welcomeImage(member);
    member.guild.channels.cache.get(welcomeChannelId).send({
      content: `<@${member.id}> Welcome to the server!`,
      files: [img],
    });
  });

  client.on("guildMemberRemove", async (member) => {
    const img = await byeImage(member);
    member.guild.channels.cache.get(welcomeChannelId).send({
      content: `<@${member.id}> Bye 👋`,
      files: [img],
    });
  });

  client.on("inviteCreate", function (invite) {
    console.log(`An invite was created`);
    console.log({ invite });
  });

  client.on("messageCreate", (message) => {
    const keys = message.content.split(" ");
    console.log(keys);
    const id = "277165188996923404";
    if (keys[0] === "!ntm" && keys.length === 1) message.send(`ntm <@${id}>`);

    if (keys[0] === "!gif" && keys.length === 1)
      message.reply(
        "!gif save [cmd_name] [gif_url] (sans les [] faut préciser pour les plus atteints)"
      );

    // private message
    // message.member.send

    // Return a list of commands on discord
    /* if (keys[0] === "!gif" && keys.length === 2 && keys[1] === "list") {
      const data = fs.readFileSync("gifs.json", "utf-8");
      const parsedData = JSON.parse(data);
      message.channel.send({
        content: parsedData.forEach(function (item) {
          console.log(item.cmd)
          return item.cmd;
        }),
      });
    } */

    if (keys[0] === "!gif" && keys.length === 4) {
      if (keys[1] === "save") {
        const data = {
          cmd: keys[2],
          content: keys[3],
        };
        const Accounts = fs.readFileSync("gifs.json", "utf-8");
        if (Accounts.length !== 0) {
          var ParsedAccounts = JSON.parse(Accounts);
        } else {
          ParsedAccounts = [];
        }
        ParsedAccounts.push(data);
        const NewData = JSON.stringify(ParsedAccounts, null, 4);
        fs.writeFileSync("gifs.json", NewData);
      }
    }

    if (keys[0] === "!gif" && keys.length === 2) {
      const data = fs.readFileSync("gifs.json", "utf-8");
      if (data.length === 0) message.reply("Command file is empty");
      const parsedData = JSON.parse(data);
      parsedData.forEach(function (item) {
        if (keys[1] === item.cmd) {
          message.reply({ content: item.content });
        }
      });
    }

    if (keys[0] === "!gif" && keys.length === 3 && keys[1] === "delete") {
      const data = fs.readFileSync("gifs.json", "utf-8");
      if (data.length === 0) message.reply("Command file is empty");
      const parsedData = JSON.parse(data);
      var index = 0;
      parsedData.forEach(function (item) {
        console.log(typeof item);

        // Check if command doesn't exist
        // if (!(keys[2] in item)) {
        //   message.reply("Command doesn't exist");
        // }
        if (keys[2] === item.cmd) {
          console.log(index);
          removeByAttr(parsedData, "cmd", item.cmd);
          const NewData = JSON.stringify(parsedData, null, 4);
          fs.writeFileSync("gifs.json", NewData);
          message.reply(`${keys[2]} command deleted successfully`);
        }
        index++;
      });
    }
  });

  client.on("typingStart", (typing) => {
    if (typing.user.username === "Ryugah") {
      typing.channel.send(`Ferme ta gueule <@${typing.member.id}>`);
    }
  });

  client.on("interactionCreate", (interaction) => {
    async function handleCommand() {
      if (!interaction.isCommand()) return;

      const slashcmd = client.slashcommands.get(interaction.commandName);
      if (!slashcmd) interaction.reply("Not a valid slash command");

      await interaction.deferReply();
      await slashcmd.run({ client, interaction });
    }
    handleCommand();
  });
  client.login(TOKEN);
}
