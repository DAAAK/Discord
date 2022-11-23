const { SlashCommandBuilder } = require("@discordjs/builders");
const { MessageEmbed } = require("discord.js");

module.exports = {
  data: new SlashCommandBuilder()
    .setName("kick")
    .setDescription("Allows the admin or owner to kick the member.")
    .addUserOption((option) =>
      option
        .setName("user")
        .setDescription("The person who you want to kick")
        .setRequired(true)
    )
    .addStringOption((option) =>
      option
        .setName("reason")
        .setDescription("Reason to kick member")
        .setRequired(true)
    ),
  run: async ({ client, interaction }) => {
    if (!interaction.isCommand()) return;
    let member = interaction.options.getMember("user");
    let reason = interaction.options.getString("reason") || "No reason given";

    if (!member) return interaction.reply("Invalid member");

    try {
      await interaction.guild.members.kick(member, reason);
      return interaction.editReply(
        `${member.user.tag} has been kicked out for ${reason}`
      );
    } catch (err) {
      if (err) {
        console.error(err);
        return interaction.editReply(`Failed to kick ${member.user.tag}`);
      }
    }
  },
};
